from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from app.domain.models import (
    AgentDecision,
    AppointmentContactContext,
    AppointmentRequest,
    AppointmentUpdate,
)
from app.repositories.appointments import SqlAppointmentService
from app.repositories.properties import SqlPropertyRepository


@dataclass(frozen=True)
class VoiceBookingResult:
    decision: AgentDecision
    appointment: dict[str, str] | None = None


class VoiceBookingFlow:
    """Per-voice-session booking state machine; contact data never enters model state."""

    def __init__(
        self, properties: SqlPropertyRepository, appointments: SqlAppointmentService
    ) -> None:
        self.properties = properties
        self.appointments = appointments
        self.phase = "idle"
        self.property_id: str | None = None
        self.property_choices: list[str] = []
        self.slots: list[datetime] = []
        self.selected_slot: datetime | None = None
        self.management_action: str | None = None
        self.management_reference: str | None = None
        self.requirements = ""

    def handle(
        self,
        text: str,
        model_decision: AgentDecision,
        selected_property_ids: list[str],
        contact: AppointmentContactContext | None,
        conversation_id: str,
        requirements: str = "",
    ) -> VoiceBookingResult | None:
        if model_decision.reason == "guardrail":
            return None
        lowered = text.casefold().strip()
        if requirements:
            self.requirements = requirements[:1000]
        if self.phase.startswith("manage_"):
            return self._manage(text, contact, conversation_id)
        if self.phase == "idle" and model_decision.kind in {"reschedule", "cancel"}:
            self.management_action = model_decision.kind
            self.management_reference = None
            self.selected_slot = None
            self.phase = "manage_reference"
            return self._manage(text, contact, conversation_id)
        if self.phase != "idle" and lowered in {
            "cancel booking",
            "cancel visit",
            "radd kar dein",
            "radd kar do",
        }:
            self.phase = "idle"
            self.property_id = None
            self.selected_slot = None
            return self._say(
                "Theek hai, voice booking process rok diya hai. Koi visit book nahi hui."
            )
        if self.phase == "idle":
            if model_decision.kind != "book":
                return None
            candidates = list(dict.fromkeys(selected_property_ids))
            candidates = [
                item for item in candidates if self.properties.get_available(item) is not None
            ]
            if not candidates:
                return self._say(
                    "Abhi conversation mein koi verified available property select nahi hui. Pehle options dekh lein, phir visit arrange karte hain."
                )
            self.property_choices = candidates[:3]
            if len(self.property_choices) > 1:
                self.phase = "property"
                labels = ("pehla", "doosra", "teesra")[: len(self.property_choices)]
                options = ", ".join(labels)
                return self._say(
                    f"Aap kis option ka visit chahte hain? {options} mein se ek bata dein."
                )
            self.property_id = self.property_choices[0]
            return self._continue_to_slots(contact)

        if self.phase == "contact":
            if contact is None:
                return self._say(
                    "Pehle neeche naam, email aur consent form complete karein; contact details chat mein share na karein."
                )
            return self._continue_to_slots(contact)

        if self.phase == "property":
            matched_prop = None
            for prop_id in self.property_choices:
                p = self.properties.get_available(prop_id)
                if p and (
                    p.area.casefold() in lowered
                    or prop_id.casefold() in lowered
                    or p.title.casefold() in lowered
                ):
                    matched_prop = prop_id
                    break
            if matched_prop:
                self.property_id = matched_prop
                return self._continue_to_slots(contact)

            choice = self._ordinal(lowered, len(self.property_choices))
            if choice is None:
                return self._say(
                    "Property select karne ke liye pehla, doosra, ya teesra option kahiye."
                )
            self.property_id = self.property_choices[choice]
            return self._continue_to_slots(contact)

        if self.phase == "slots":
            if contact is None:
                return self._say(
                    "Visit arrange karne se pehle neeche naam, email aur consent form complete kar dein."
                )
            choice = self._ordinal(lowered, len(self.slots))
            if choice is None:
                return self._say(
                    "In available times mein se ek choose karein: " + self._slot_phrase()
                )
            self.selected_slot = self.slots[choice]
            self.phase = "confirm"
            item = self.properties.get_available(self.property_id or "")
            title = item.title if item else "selected property"
            return self._say(
                f"Confirm kar dein: {title} ka visit {self._spoken_time(self.selected_slot)} par book karoon? Sirf haan ya nahin kahiye."
            )

        if self.phase == "confirm":
            if self._is_confirmation(lowered):
                if contact is None or self.property_id is None or self.selected_slot is None:
                    self.phase = "idle"
                    return self._say(
                        "Contact consent ya selected visit details missing hain. Form check karke dobara request karein."
                    )
                item = self.properties.get_available(self.property_id)
                if item is None:
                    self.phase = "idle"
                    return self._say(
                        "Yeh property ab available nahi hai, is liye visit book nahi hui. Main current options dobara check kar sakta hoon."
                    )
                key = uuid5(
                    NAMESPACE_URL,
                    f"awaaz-voice-booking:{conversation_id}:{self.property_id}:{self.selected_slot.isoformat()}",
                )
                request = AppointmentRequest(
                    property_id=self.property_id,
                    employee=item.assigned_employee,
                    starts_at=self.selected_slot,
                    client_name=contact.client_name,
                    contact_email=contact.contact_email,
                    contact_phone=contact.contact_phone,
                    idempotency_key=key,
                    consent=contact.consent,
                    requirements=self.requirements,
                    meeting_notes="Property viewing requested and explicitly confirmed during voice conversation.",
                )
                try:
                    appointment = self.appointments.book(request)
                except ValueError:
                    self.phase = "slots"
                    self.slots = self.appointments.available_slots(self.property_id)
                    return self._say(
                        "Maazrat, yeh slot abhi reserve nahi ho saka. Main current available times dobara dekh raha hoon: "
                        + self._slot_phrase()
                    )
                self.phase = "idle"
                result = {
                    "status": "pending_calendar",
                    "reference": appointment.reference,
                    "property_id": item.id,
                    "starts_at": appointment.starts_at.isoformat(),
                }
                return VoiceBookingResult(
                    AgentDecision(
                        kind="book",
                        spoken_text=(
                            "Ji, visit request record ho gayi. Calendar confirmation pending hai. "
                            f"Reference {appointment.reference} hai."
                        ),
                    ),
                    result,
                )
            if self._is_rejection(lowered):
                self.phase = "slots"
                self.selected_slot = None
                return self._say(
                    "Theek hai, visit book nahi ki. Available times mein se doosra option choose kar sakte hain: "
                    + self._slot_phrase()
                )
            return self._say(
                "Booking se pehle clear confirmation chahiye. Kya main yeh visit book karoon? Haan ya nahin kahiye."
            )

        return self._say("Visit booking state reset ho gayi. Dobara visit request kar dein.")

    def _manage(
        self, text: str, contact: AppointmentContactContext | None, conversation_id: str
    ) -> VoiceBookingResult:
        lowered = text.casefold().strip()
        if lowered in {"stop", "never mind", "rehne dein", "abort"}:
            self.phase = "idle"
            return self._say("Theek hai, appointment mein koi tabdeeli nahi ki.")
        reference_match = re.search(r"\bAES[ -]?([a-fA-F0-9]{10})\b", text, re.IGNORECASE)
        if self.phase in {"manage_contact", "manage_reference"}:
            if reference_match:
                self.management_reference = "AES-" + reference_match.group(1).upper()
            if contact is None:
                self.phase = "manage_contact"
                return self._say(
                    "Pehle neeche consent form mein booking wali email aur naam dein. "
                    "Phir appointment ka AES reference boliye ya type karein; email awaaz mein share na karein."
                )
            if self.management_reference is None:
                self.phase = "manage_reference"
                return self._say(
                    "Kaunsi appointment? Confirmation wala poora AES reference boliye ya type karein."
                )
            try:
                appointment = self.appointments.get_for_contact(
                    self.management_reference, str(contact.contact_email)
                )
            except ValueError:
                self.management_reference = None
                self.phase = "manage_reference"
                return self._say(
                    "Reference aur consent form ki email match nahi hue. Booking wali email aur reference check karein; koi tabdeeli nahi hui."
                )
            if appointment.status == "cancelled":
                self.phase = "idle"
                return self._say(
                    "Yeh appointment pehle hi cancel hai. Naye visit ke liye nayi booking request karein."
                )
            self.property_id = appointment.property_id
            if self.management_action == "cancel":
                self.phase = "manage_confirm"
                return self._say(
                    f"Confirm karein: reference {appointment.reference}, {self._spoken_time(appointment.starts_at)} ka visit cancel karoon? Haan ya nahin kahiye."
                )
            self.slots = self.appointments.available_slots(appointment.property_id)
            if not self.slots:
                self.phase = "idle"
                return self._say(
                    "Is property ke liye koi verified naya slot nahi mila. Purani appointment unchanged hai."
                )
            self.phase = "manage_slots"
            return self._say(
                "Naya time select karein: "
                + self._slot_phrase()
                + ". Purani appointment abhi unchanged hai."
            )
        if self.phase == "manage_slots":
            choice = self._ordinal(lowered, len(self.slots))
            if choice is None:
                return self._say("Naye time ka option choose karein: " + self._slot_phrase())
            self.selected_slot = self.slots[choice]
            self.phase = "manage_confirm"
            return self._say(
                f"Reference {self.management_reference} ko {self._spoken_time(self.selected_slot)} par reschedule karoon? Haan ya nahin kahiye."
            )
        if self.phase == "manage_confirm":
            confirmation = (
                re.sub(r"\bcancel\b", "", lowered).strip()
                if self.management_action == "cancel"
                else lowered
            )
            if self._is_rejection(confirmation):
                self.phase = "idle"
                return self._say("Theek hai, appointment mein koi tabdeeli nahi ki.")
            if not self._is_confirmation(confirmation):
                return self._say(
                    "Tabdeeli se pehle clear confirmation chahiye. Haan ya nahin kahiye."
                )
            if contact is None or self.management_reference is None:
                self.phase = "manage_contact"
                return self._say(
                    "Booking wali contact email aur consent form dobara complete karein; koi tabdeeli nahi hui."
                )
            reference = self.management_reference
            action = self.management_action
            key = uuid5(
                NAMESPACE_URL,
                f"awaaz-voice-update:{conversation_id}:{action}:{reference}:{self.selected_slot}",
            )
            try:
                result = self.appointments.update(
                    AppointmentUpdate(
                        reference=reference,
                        contact_email=contact.contact_email,
                        starts_at=self.selected_slot,
                        idempotency_key=key,
                    ),
                    cancel=action == "cancel",
                )
            except ValueError:
                self.phase = "manage_reference"
                self.management_reference = None
                return self._say(
                    "Identity ya slot dobara verify nahi ho saka. Tabdeeli confirm nahi hui; reference aur current availability dobara check karein."
                )
            self.phase = "idle"
            verb = "cancellation" if action == "cancel" else "reschedule"
            return VoiceBookingResult(
                AgentDecision(
                    kind=action,
                    spoken_text=f"Ji, {verb} request reference {reference} ke liye record ho gayi. Calendar aur employee email update pending hai.",
                ),
                {
                    "reference": reference,
                    "property_id": result.property_id,
                    "starts_at": result.starts_at.isoformat(),
                    "status": "pending_calendar",
                    "action": verb,
                },
            )
        self.phase = "idle"
        return self._say("Appointment management reset ho gayi; koi tabdeeli nahi ki.")

    def _continue_to_slots(self, contact: AppointmentContactContext | None) -> VoiceBookingResult:
        if contact is None:
            self.phase = "contact"
            return self._say(
                "Visit ke liye neeche apna naam aur consented email form mein complete karke consent dein; phir boliye continue."
            )
        self.slots = self.appointments.available_slots(self.property_id or "")
        if not self.slots:
            self.phase = "idle"
            return self._say(
                "Is property ke assigned employee ke paas aglay available hours mein koi verified slot nahi mila. Human callback arrange kar sakte hain."
            )
        self.phase = "slots"
        return self._say(
            "Yeh verified available times hain: "
            + self._slot_phrase()
            + ". Ek option choose karein."
        )

    def refresh_contact(
        self, contact: AppointmentContactContext | None
    ) -> VoiceBookingResult | None:
        if self.phase != "contact" or contact is None:
            return None
        self.slots = self.appointments.available_slots(self.property_id or "")
        if not self.slots:
            self.phase = "idle"
            return self._say(
                "Consent mil gaya, lekin abhi available visit slot nahi mila. Human callback arrange kar sakte hain."
            )
        self.phase = "slots"
        return self._say(
            "Consent mil gaya. Yeh verified available times hain: "
            + self._slot_phrase()
            + ". Ek option choose karein."
        )

    def _slot_phrase(self) -> str:
        labels = ("pehla", "doosra", "teesra")
        return "; ".join(
            f"{labels[index]}: {self._spoken_time(slot)}"
            for index, slot in enumerate(self.slots[:3])
        )

    @staticmethod
    def _spoken_time(value: datetime) -> str:
        local = value.astimezone(ZoneInfo("Asia/Karachi"))
        return local.strftime("%A %d %B, %I:%M %p PKT")

    @staticmethod
    def _ordinal(text: str, total: int) -> int | None:
        if re.fullmatch(r"\s*[1-3]\s*", text):
            value = int(text) - 1
            return value if 0 <= value < total else None

        patterns = [
            (0, r"\b(first|pehla|pehli|pahla|pahli|one|1|opt(?:ion)?\s*1)\b"),
            (1, r"\b(second|doosra|doosri|dosra|dusra|two|2|opt(?:ion)?\s*2)\b"),
            (2, r"\b(third|teesra|teesri|tisra|three|3|opt(?:ion)?\s*3)\b"),
        ]
        for idx, pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return idx if 0 <= idx < total else None
        return None

    @staticmethod
    def _is_confirmation(text: str) -> bool:
        if VoiceBookingFlow._is_rejection(text):
            return False
        if text in {
            "yes",
            "yes please",
            "haan",
            "han",
            "jee haan",
            "ji haan",
            "ji han",
            "confirm",
            "confirm it",
            "book it",
            "kar dein",
            "kar do",
            "theek hai",
            "bilkul",
        }:
            return True
        return bool(
            re.search(
                r"\b(yes|haan|han|jee haan|ji haan|ji han|confirm|book it|kar dein|kar do|kar dain|theek hai|bilkul)\b",
                text,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _is_rejection(text: str) -> bool:
        if text in {
            "no",
            "no thanks",
            "nahin",
            "nahi",
            "na",
            "cancel",
            "mat karein",
            "mat karo",
            "rehne dein",
        }:
            return True
        return bool(
            re.search(
                r"\b(no|not|don.t|nahin|nahi|na|cancel|mat karein|mat karo|rehne dein|rehney do)\b",
                text,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _say(text: str) -> VoiceBookingResult:
        return VoiceBookingResult(AgentDecision(kind="ask_clarification", spoken_text=text))
