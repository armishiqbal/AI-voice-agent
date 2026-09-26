/** Voice calls must use a ready server provider; never start browser-only recognition. */
export function resolveLiveVoiceAction(voiceReady: boolean): "connect" | "blocked" {
  return voiceReady ? "connect" : "blocked";
}

/** Intentional stops must not let an old socket overwrite the next call's UI. */
export function closeVoiceSession(
  socket: Pick<WebSocket, "close" | "onopen" | "onclose" | "onerror" | "onmessage"> | null,
): void {
  if (!socket) return;
  socket.onopen = null;
  socket.onclose = null;
  socket.onerror = null;
  socket.onmessage = null;
  socket.close(1000, "User ended voice chat");
}
