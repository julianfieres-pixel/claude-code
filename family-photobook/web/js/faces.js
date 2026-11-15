// Face detection + recognition in the browser (face-api / TensorFlow.js). Nothing leaves the device.
import * as faceapi from '../vendor/face-api.esm.js';

const MODEL_URL = new URL('../vendor/models/', import.meta.url).href;
// face-api descriptors: Euclidean distance < 0.6 = same person (library default).
// We cluster a bit stricter so groups stay clean, and assign a bit looser.
export const CLUSTER_DIST = 0.48;
export const MATCH_DIST = 0.52;

let ready;
export function loadModels() {
  if (!ready) {
    ready = (async () => {
      try { await faceapi.tf.setBackend('webgl'); } catch { await faceapi.tf.setBackend('cpu'); }
      await faceapi.tf.ready();
      await Promise.all([
        faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
        faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
        faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL),
      ]);
      return faceapi.tf.getBackend();
    })();
  }
  return ready;
}

const detectorOptions = () => new faceapi.SsdMobilenetv1Options({ minConfidence: 0.5, maxResults: 30 });

/** Detect faces on a canvas. Returns [{box:[x,y,w,h] relative, det, happy, desc:number[128], crop:Blob}] */
export async function detectFaces(canvas) {
  const results = await faceapi.detectAllFaces(canvas, detectorOptions())
    .withFaceLandmarks().withFaceDescriptors().withFaceExpressions();
  const W = canvas.width, H = canvas.height;
  const faces = [];
  for (const r of results) {
    const b = r.detection.box;
    if (b.width < 24 || b.height < 24) continue; // too small to recognise reliably
    faces.push({
      box: [b.x / W, b.y / H, b.width / W, b.height / H],
      det: +r.detection.score.toFixed(3),
      happy: +(r.expressions.happy || 0).toFixed(3),
      desc: Array.from(r.descriptor, v => +v.toFixed(5)),
      crop: await cropFace(canvas, b),
    });
  }
  return faces;
}

async function cropFace(canvas, b) {
  const pad = 0.35;
  const s = Math.max(b.width, b.height) * (1 + pad * 2);
  const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
  const c = document.createElement('canvas');
  c.width = c.height = 112;
  c.getContext('2d').drawImage(canvas, cx - s / 2, cy - s / 2, s, s, 0, 0, 112, 112);
  return new Promise(r => c.toBlob(r, 'image/jpeg', 0.8));
}

export function dist(a, b) {
  let s = 0;
  for (let i = 0; i < a.length; i++) { const d = a[i] - b[i]; s += d * d; }
  return Math.sqrt(s);
}

/**
 * Group all faces into clusters of the same person (leader clustering on running centroids).
 * faces: [{photoId, idx, face}] -> [{id, centroid, members:[...]}] sorted by size.
 */
export function clusterFaces(faces) {
  const clusters = [];
  for (const f of faces) {
    let best = null, bestD = Infinity;
    for (const c of clusters) {
      const d = dist(f.face.desc, c.centroid);
      if (d < bestD) { bestD = d; best = c; }
    }
    if (best && bestD < CLUSTER_DIST) {
      const n = best.members.length;
      best.centroid = best.centroid.map((v, i) => (v * n + f.face.desc[i]) / (n + 1));
      best.members.push(f);
    } else {
      clusters.push({ centroid: f.face.desc.slice(), members: [f] });
    }
  }
  clusters.sort((a, b) => b.members.length - a.members.length);
  clusters.forEach((c, i) => {
    c.id = i;
    // representative: biggest, most confident face
    c.rep = c.members.reduce((a, b) => (b.face.box[2] * b.face.det > a.face.box[2] * a.face.det ? b : a));
  });
  return clusters;
}

/**
 * refs: [{person: 'a'|'b'|'c'|'other', desc:number[]}] (labelled cluster centroids).
 * Returns person key or null for a face descriptor.
 */
export function identify(desc, refs) {
  let best = null, bestD = Infinity;
  for (const r of refs) {
    const d = dist(desc, r.desc);
    if (d < bestD) { bestD = d; best = r; }
  }
  if (!best || bestD > MATCH_DIST || best.person === 'other') return { person: null, d: bestD };
  return { person: best.person, d: bestD };
}

export function labelForCluster(cluster, refs) {
  const { person, d } = identify(cluster.centroid, refs);
  if (person) return person;
  // explicitly marked as "someone else"
  const other = refs.filter(r => r.person === 'other').some(r => dist(r.desc, cluster.centroid) < CLUSTER_DIST);
  return other ? 'other' : (d < MATCH_DIST ? 'other' : null);
}
