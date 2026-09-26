import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";

const source = await readFile(new URL("../src/pcmCaptureWorklet.js", import.meta.url), "utf8");

test("audio worklet emits the same 4096-sample frames and stops cleanly", () => {
  const emitted = [];
  let Processor;
  class AudioWorkletProcessor {
    constructor() {
      this.port = {
        onmessage: null,
        postMessage(frame, transfer) {
          emitted.push({ frame, transfer });
        },
      };
    }
  }
  runInNewContext(source, {
    AudioWorkletProcessor,
    Float32Array,
    registerProcessor(name, processorClass) {
      assert.equal(name, "pcm-capture-processor");
      Processor = processorClass;
    },
  });

  const processor = new Processor();
  for (let index = 0; index < 32; index += 1) {
    assert.equal(processor.process([[new Float32Array(128).fill(index / 32)]]), true);
  }
  assert.equal(emitted.length, 1);
  assert.equal(emitted[0].frame.length, 4096);
  assert.equal(emitted[0].frame[0], 0);
  assert.equal(emitted[0].frame[4095], 31 / 32);
  assert.equal(emitted[0].transfer[0], emitted[0].frame.buffer);

  processor.port.onmessage({ data: { type: "stop" } });
  assert.equal(processor.process([[new Float32Array(128)]]), false);
  assert.equal(emitted.length, 1);
});
