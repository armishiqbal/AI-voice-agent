const FRAME_SIZE = 4096;

class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frame = new Float32Array(FRAME_SIZE);
    this.offset = 0;
    this.active = true;
    this.port.onmessage = (event) => {
      if (event.data?.type === "stop") this.active = false;
    };
  }

  process(inputs) {
    if (!this.active) return false;
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    let offset = 0;
    while (offset < channel.length) {
      const length = Math.min(FRAME_SIZE - this.offset, channel.length - offset);
      this.frame.set(channel.subarray(offset, offset + length), this.offset);
      this.offset += length;
      offset += length;
      if (this.offset === FRAME_SIZE) {
        const completed = this.frame;
        this.port.postMessage(completed, [completed.buffer]);
        this.frame = new Float32Array(FRAME_SIZE);
        this.offset = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-capture-processor", PcmCaptureProcessor);
