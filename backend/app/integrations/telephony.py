from __future__ import annotations

import base64
import hashlib
import hmac
import sys
import urllib.parse
from array import array
from dataclasses import dataclass
from html import escape
from typing import Protocol


class TelephonyProviderError(RuntimeError):
    """Expected telephony boundary failure; no fake call is created."""


@dataclass(frozen=True)
class TelephonySession:
    call_id: str
    websocket_url: str


class TelephonyAdapter(Protocol):
    async def start_session(self, destination: str) -> TelephonySession: ...


class UnavailableTelephonyAdapter:
    """Explicit adapter boundary for a later carrier/phone-number integration."""

    async def start_session(self, destination: str) -> TelephonySession:
        del destination
        raise TelephonyProviderError(
            "Telephony adapter is not configured for the browser-first release"
        )


class TwilioTelephonyAdapter:
    """Twilio REST/webhook boundary for optional phone sessions.

    The adapter creates calls only when every required credential and public URL is present.
    Media itself is handled by the FastAPI WebSocket bridge, keeping carrier concerns outside
    the LangGraph and appointment services.
    """

    def __init__(
        self,
        account_sid: str | None,
        auth_token: str | None,
        from_number: str | None,
        public_base_url: str | None,
    ) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None

    def _require_config(self) -> None:
        if not all((self.account_sid, self.auth_token, self.from_number, self.public_base_url)):
            raise TelephonyProviderError(
                "Twilio telephony requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                "TWILIO_FROM_NUMBER, and TELEPHONY_PUBLIC_BASE_URL"
            )

    async def start_session(self, destination: str) -> TelephonySession:
        self._require_config()
        if not destination.strip():
            raise TelephonyProviderError("A destination phone number is required")
        try:
            import httpx
        except ImportError as error:
            raise TelephonyProviderError(
                "Install the telephony extra to enable Twilio calls"
            ) from error
        voice_url = f"{self.public_base_url}/v1/telephony/inbound"
        endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls.json"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    endpoint,
                    data={"To": destination, "From": self.from_number, "Url": voice_url},
                    auth=(self.account_sid, self.auth_token),
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as error:
            raise TelephonyProviderError(f"Twilio call creation failed: {error}") from error
        call_id = str(payload.get("sid", ""))
        if not call_id:
            raise TelephonyProviderError("Twilio did not return a call SID")
        return TelephonySession(call_id=call_id, websocket_url=self.media_url())

    def media_url(self) -> str:
        self._require_config()
        parsed = urllib.parse.urlsplit(self.public_base_url or "")
        scheme = "wss" if parsed.scheme == "https" else "ws"
        # Twilio Media Streams reject query strings in the <Stream> URL. The
        # CallSid is supplied in Twilio's WebSocket `start` event, so it does
        # not need to be copied into the URL.
        return f"{scheme}://{parsed.netloc}/v1/telephony/media"

    def inbound_twiml(self) -> str:
        """Return TwiML that connects the call to the signed media WebSocket."""

        self._require_config()
        stream_url = self.media_url()
        escaped_url = escape(stream_url, quote=True)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Connect><Stream url="'
            f"{escaped_url}"
            '"/></Connect></Response>'
        )

    @staticmethod
    def verify_signature(
        url: str,
        params: dict[str, str],
        signature: str | None,
        auth_token: str | None,
    ) -> bool:
        """Verify Twilio's HMAC-SHA1 request signature without trusting caller input."""

        if not signature or not auth_token:
            return False
        canonical = url + "".join(f"{key}{params[key]}" for key in sorted(params))
        digest = hmac.new(auth_token.encode(), canonical.encode(), hashlib.sha1).digest()
        expected = base64.b64encode(digest).decode()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def verify_websocket_signature(url: str, signature: str | None, auth_token: str | None) -> bool:
        """Validate a Twilio WSS handshake, allowing its documented slash variant."""

        canonical_url = url.rstrip("/")
        return TwilioTelephonyAdapter.verify_signature(
            canonical_url, {}, signature, auth_token
        ) or TwilioTelephonyAdapter.verify_signature(f"{canonical_url}/", {}, signature, auth_token)


def build_telephony_adapter(config: object) -> TelephonyAdapter:
    provider = str(getattr(config, "telephony_provider", "none")).casefold()
    if provider == "twilio":
        return TwilioTelephonyAdapter(
            account_sid=getattr(config, "twilio_account_sid", None),
            auth_token=getattr(config, "twilio_auth_token", None),
            from_number=getattr(config, "twilio_from_number", None),
            public_base_url=getattr(config, "telephony_public_base_url", None),
        )
    return UnavailableTelephonyAdapter()


_ULAW_BIAS = 0x84
_ULAW_CLIP = 32635


def mulaw_to_pcm16(data: bytes) -> bytes:
    """Decode Twilio's 8 kHz G.711 μ-law frames to little-endian PCM16."""

    samples = array("h")
    for encoded in data:
        value = (~encoded) & 0xFF
        sign = value & 0x80
        exponent = (value >> 4) & 0x07
        mantissa = value & 0x0F
        sample = ((mantissa << 3) + _ULAW_BIAS) << exponent
        sample -= _ULAW_BIAS
        samples.append(-sample if sign else sample)
    if samples.itemsize != 2:
        raise TelephonyProviderError("Unsupported host PCM16 representation")
    if samples.tobytes() and sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def pcm16_to_mulaw(data: bytes) -> bytes:
    """Encode little-endian PCM16 frames for Twilio's outbound media stream."""

    if len(data) % 2:
        raise TelephonyProviderError("PCM16 payload must contain complete samples")
    samples = array("h")
    samples.frombytes(data)
    if sys.byteorder != "little":
        samples.byteswap()
    encoded = bytearray()
    for sample in samples:
        sign = 0x80 if sample < 0 else 0
        magnitude = min(abs(sample), _ULAW_CLIP) + _ULAW_BIAS
        exponent = 7
        mask = 0x4000
        while exponent > 0 and not (magnitude & mask):
            exponent -= 1
            mask >>= 1
        mantissa = (magnitude >> (exponent + 3)) & 0x0F
        encoded.append((~(sign | (exponent << 4) | mantissa)) & 0xFF)
    return bytes(encoded)


def resample_pcm16(data: bytes, input_rate: int, output_rate: int) -> bytes:
    """Linear-resample PCM16 bytes for the carrier's 8 kHz media contract."""

    if input_rate <= 0 or output_rate <= 0 or len(data) % 2:
        raise TelephonyProviderError("Invalid PCM16 resampling input")
    if input_rate == output_rate:
        return data
    source = array("h")
    source.frombytes(data)
    if sys.byteorder != "little":
        source.byteswap()
    if not source:
        return b""
    output_count = max(1, round(len(source) * output_rate / input_rate))
    output = array("h")
    ratio = input_rate / output_rate
    for index in range(output_count):
        position = index * ratio
        left = min(int(position), len(source) - 1)
        right = min(left + 1, len(source) - 1)
        fraction = position - left
        sample = round(source[left] * (1 - fraction) + source[right] * fraction)
        output.append(max(-32768, min(32767, sample)))
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()
