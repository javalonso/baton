/**
 * Speaking instead of typing.
 *
 * Uses the browser's own speech recognition. Nothing is uploaded by Baton: the transcript
 * arrives as text and the audio never leaves the device through us. Note that in Chrome the
 * recognition itself is a Google service, which is a real consideration for health notes and
 * is why `Recorder` is a seam -- swapping this for Amazon Transcribe changes this file and
 * nothing else.
 *
 * Not every browser has it. `available` says so up front, so V3 can offer the keyboard
 * rather than a button that does nothing.
 */

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
};

function constructor(): (new () => SpeechRecognitionLike) | null {
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const available = (): boolean => constructor() !== null;

export type Recorder = {
  start: () => void;
  stop: () => void;
};

export function listen(
  locale: "es" | "en",
  onText: (text: string, final: boolean) => void,
  onEnd: () => void,
): Recorder | null {
  const Recognition = constructor();
  if (!Recognition) return null;

  const recognition = new Recognition();
  recognition.lang = locale === "es" ? "es-MX" : "en-US";
  // A visit note is somebody thinking out loud with pauses in it. Stopping at the first
  // silence would cut them off mid-sentence, which is how you get half a note.
  recognition.continuous = true;
  recognition.interimResults = true;

  let settled = "";
  recognition.onresult = (event: any) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i];
      if (result.isFinal) settled += result[0].transcript;
      else interim += result[0].transcript;
    }
    onText((settled + interim).trim(), false);
  };
  recognition.onerror = () => onEnd();
  recognition.onend = () => {
    onText(settled.trim(), true);
    onEnd();
  };

  return {
    start: () => recognition.start(),
    stop: () => recognition.stop(),
  };
}
