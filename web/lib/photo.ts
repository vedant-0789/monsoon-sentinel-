"use client";

/**
 * On-device photo checks.
 * 1. downscale(): resize to <= 1024 px and re-encode as JPEG. Redrawing on a canvas also
 *    drops EXIF metadata (GPS location, device) before anything leaves the phone.
 * 2. floodProbability(): runs the same ONNX model the server uses (MobileNetV3-Small +
 *    logistic head, trained on Flood10k) inside the browser via onnxruntime-web.
 */

const ORT_VERSION = "1.31.1";
const MODEL_URL = "/models/photo_verifier.onnx";

type Ort = typeof import("onnxruntime-web");
let sessionPromise: Promise<{ ort: Ort; session: import("onnxruntime-web").InferenceSession }> | null = null;

function session() {
  if (!sessionPromise) {
    sessionPromise = (async () => {
      const ort = await import("onnxruntime-web");
      ort.env.wasm.wasmPaths = `https://cdn.jsdelivr.net/npm/onnxruntime-web@${ORT_VERSION}/dist/`;
      ort.env.wasm.numThreads = 1;
      const s = await ort.InferenceSession.create(MODEL_URL, { executionProviders: ["wasm"] });
      return { ort, session: s };
    })();
    sessionPromise.catch(() => {
      sessionPromise = null;
    });
  }
  return sessionPromise;
}

function loadImage(file: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not read this image"));
    };
    img.src = url;
  });
}

export async function downscale(file: Blob, maxSide = 1024): Promise<{ dataUrl: string; img: HTMLImageElement }> {
  const img = await loadImage(file);
  const s = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
  const c = document.createElement("canvas");
  c.width = Math.round(img.naturalWidth * s);
  c.height = Math.round(img.naturalHeight * s);
  c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
  const dataUrl = c.toDataURL("image/jpeg", 0.82);
  return { dataUrl, img: await loadImage(await (await fetch(dataUrl)).blob()) };
}

/** Same preprocessing as the server: short side 256, centre crop 224, RGB in [0,1], NCHW. */
function toTensor(ort: Ort, img: HTMLImageElement) {
  const w = img.naturalWidth;
  const h = img.naturalHeight;
  const s = 256 / Math.min(w, h);
  const rw = Math.max(224, Math.round(w * s));
  const rh = Math.max(224, Math.round(h * s));
  const c = document.createElement("canvas");
  c.width = 224;
  c.height = 224;
  const ctx = c.getContext("2d")!;
  ctx.drawImage(img, -Math.floor((rw - 224) / 2), -Math.floor((rh - 224) / 2), rw, rh);
  const { data } = ctx.getImageData(0, 0, 224, 224);
  const out = new Float32Array(3 * 224 * 224);
  for (let i = 0; i < 224 * 224; i++) {
    out[i] = data[i * 4] / 255;
    out[224 * 224 + i] = data[i * 4 + 1] / 255;
    out[2 * 224 * 224 + i] = data[i * 4 + 2] / 255;
  }
  return new ort.Tensor("float32", out, [1, 3, 224, 224]);
}

export async function floodProbability(img: HTMLImageElement): Promise<number> {
  const { ort, session: s } = await session();
  const res = await s.run({ [s.inputNames[0]]: toTensor(ort, img) });
  return Number((res[s.outputNames[0]].data as Float32Array)[0]);
}
