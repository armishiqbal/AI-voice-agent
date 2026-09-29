export function voiceModeForLanguage(language) {
  return language === "en" || language === "ur-Latn" || language === "ur-Arab" ? "hybrid" : "openai";
}
