/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

const DEFAULT_MODELS = [
  // "image-classification",
  // Error: Error: Could not locate file: "https://model-hub.mozilla.org/Xenova/vit-base-patch16-224/default/preprocessor_config.json".
  // is replaced with https://huggingface.co/Xenova/vit-base-patch16-224-in21k
  // "image-segmentation",
  // "zero-shot-image-classification",
  // https://github.com/huggingface/transformers.js/issues/955
  /*
  �[0;93m2025-01-02 12:25:25.385938 [W:onnxruntime:, constant_folding.cc:268 ApplyImpl] Could not find a CPU kernel and hence can't constant fold Exp node '/Exp'�[m
    Hc :100
    <anonymous> line 26 > WebAssembly.instantiate:17014471
    <anonymous> line 26 > WebAssembly.instantiate:2266941
    <anonymous> line 26 > WebAssembly.instantiate:802831
    <anonymous> line 26 > WebAssembly.instantiate:16987174
    <anonymous> line 26 > WebAssembly.instantiate:593201
    <anonymous> line 26 > WebAssembly.instantiate:54812
    <anonymous> line 26 > WebAssembly.instantiate:20680488
    <anonymous> line 26 > WebAssembly.instantiate:88110
    <anonymous> line 26 > WebAssembly.instantiate:8919686
    <anonymous> line 26 > WebAssembly.instantiate:1210123
    <anonymous> line 26 > WebAssembly.instantiate:2921096
    <anonymous> line 26 > WebAssembly.instantiate:2459959
    <anonymous> line 26 > WebAssembly.instantiate:16697504
    <anonymous> line 26 > WebAssembly.instantiate:11495879
    Pd/b[c]< :79
    _OrtCreateSession :111
    createSession chrome://global/content/ml/ort.webgpu-dev.mjs:15480
    createSession2 chrome://global/content/ml/ort.webgpu-dev.mjs:16092
    loadModel chrome://global/content/ml/ort.webgpu-dev.mjs:16206
    createInferenceSessionHandler chrome://global/content/ml/ort.webgpu-dev.mjs:16321
    create chrome://global/content/ml/ort.webgpu-dev.mjs:1179
  */
  // "object-detection", // Ok but doesn't detect anythng
  // "zero-shot-object-detection",
  // "image-to-image",
  // "depth-estimation",
  // "feature-extraction",
  // "image-feature-extraction",
  "image-to-text",
  // "text-generation",
  // "text-classification",
  // "summarization",
  // "translation",
  // "text2text-generation",
  // "zero-shot-classification",
  // "token-classification",
  // "document-question-answering",
  // "question-answering",
  // // "fill-mask",
];

const taskToModel = {
  // "image-classification": {
  //   modelHub: "huggingface",
  //   modelRevision: "main",
  //   modelId: "aaraki/vit-base-patch16-224-in21k-finetuned-cifar10",
  //   dtype: "fp32",
  //   taskName: "image-classification",
  // },
  // "image-segmentation": {
  //   modelHub: "huggingface",
  //   modelRevision: "main",
  //   modelId: "facebook/mask2former-swin-large-cityscapes-panoptic",
  //   dtype: "fp32",
  //   taskName: "image-segmentation",
  // },
  // "image-classification": {
  //   taskName: "image-classification",
  //   modelRevision: "main",
  // },
  // "image-segmentation": {
  //   taskName: "image-segmentation",
  //   modelRevision: "main",
  // },
  // "zero-shot-image-classification": {
  //     taskName: "zero-shot-image-classification",
  //     modelRevision: "main",
  // },
  // "object-detection": {
  //   taskName: "object-detection",
  //   modelRevision: "main",
  // },
  // "zero-shot-object-detection": {
  //   taskName: "zero-shot-object-detection",
  //   modelRevision: "main",
  // },
  // "image-to-image": {
  //   taskName: "image-to-image",
  //   modelRevision: "main",
  // },
  // "depth-estimation": {
  //   taskName: "depth-estimation",
  //   modelRevision: "main",
  // },
  // "feature-extraction": {
  //   taskName: "feature-extraction",
  //   modelRevision: "main",
  // },
  // "image-feature-extraction": {
  //   taskName: "image-feature-extraction",
  //   modelRevision: "main",
  // },
  "image-to-text": {
    taskName: "image-to-text",
    modelRevision: "main",
  },  
};

var firstRun = true;

function createImageSample() {
  // Desired dimensions
  const width = 224;
  const height = 224;

  // Create an offscreen canvas
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");

  // Create an ImageData object to manipulate pixels
  const imageData = ctx.createImageData(width, height);
  const data = imageData.data; // a Uint8ClampedArray of RGBA values

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const sineVal =
        Math.sin((2 * Math.PI * x) / width) *
        Math.sin((2 * Math.PI * y) / height);

      // Map sineVal from [-1,1] to [0,255]
      const grayscale = (sineVal + 1) * 127.5;

      // Compute the index in the array (4 bytes per pixel: RGBA)
      const idx = (y * width + x) * 4;

      data[idx + 0] = grayscale;  // R
      data[idx + 1] = grayscale;  // G
      data[idx + 2] = grayscale;  // B
      data[idx + 3] = 255;        // A (fully opaque)
    }
  }

  // Place the pixels into the canvas
  ctx.putImageData(imageData, 0, 0);

  const result = canvas.toDataURL("image/jpeg", 0.01);
  return result;
}

async function useModels() {
  const results = [];

  const listener = progressData => {
    results.push(progressData);
  };

  browser.trial.ml.onProgress.addListener(listener);

  try {
    if (firstRun) {
      for (const taskName of DEFAULT_MODELS) {
        results.push("Loading " + taskName);
        const opts = taskToModel[taskName];
        await browser.trial.ml.createEngine(opts);
      }
      results.push("Model loading done!");
      firstRun = false;
    }

    // const jpegDataUrl = createImageSample();

    // const WITH_IMAGE_INPUT = {
      // "image-classification": {
      //   args: [
      //     "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg"
      //   ],
      // },
      // "image-segmentation": {
      //   args: [
      //     "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg"
      //   ],
      // },
      // "zero-shot-image-classification": {
      //   args: [
      //     "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg",
      //     ["animals", "nature"]
      //   ],
      // },
      // "object-detection": {
      //   args: [
      //     "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg"
      //   ],
      // },
      // "zero-shot-object-detection": {
      //   args: [
      //     "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg",
      //     ["tiger"]
      //   ],
      // },
      // "image-to-image": {
      //   args: [
      //     "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg"
      //   ],
      // },
      // "depth-estimation": {
      //   args: [
      //     "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg"
      //   ],
      // },
      // "feature-extraction": {
      //   args: [
      //     "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg"
      //   ],
      // },
      // "image-feature-extraction": {
      //   args: [
      //     "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg"
      //   ],
      // },
    //   "image-to-text": {
    //     args: [
    //       "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg"
    //       // jpegDataUrl 
    //     ],
    //     options: {
    //       max_new_tokens: 300,
    //     }
    //   },
    // };

    // for (const modelName of Object.keys(WITH_IMAGE_INPUT)) {
    //   results.push("Running " + modelName);
    //   const args = WITH_IMAGE_INPUT[modelName];
    //   const result = await browser.trial.ml.runEngine(args);
    //   results.push({results: {name: modelName, data: JSON.stringify(result)}});
    // }

    // results.push("Image model running done!");

    /*
    const enhancedText = await (async () => {
      const engine = engines["text-generation"];
      const seedText = imgInputResults["image-to-text"];
      return await engine.run({
        args: [seedText],
        options: {
          max_new_tokens: 1048576,
        }});
    })();

    console.log("Generated text length in chars " + enhancedText.length);

    const WITH_TEXT_INPUT = [
      "text-classification",
      "summarization",
      "translation",
      "text2text-generation",
      "zero-shot-classification",
      "token-classification",
    ];

    const txtInputResults = new Map();
    for (const modelName of WITH_TEXT_INPUT) {
      const result = await (async () => {
        const engine = engines[modelName];
        return await engine.run({
          args: [enhancedText],
          options: {
            max_new_tokens: 1048576,
          },
        });
      })();
      txtInputResults.set(modelName, result);
    }

    const question = "In what sense can we be certain that knowledge exists?";
    const WITH_QUESTION_INPUT = [
      "document-question-answering",
      "question-answering",
    ];

    const questionInputResults = new Map();
    for (const modelName of WITH_QUESTION_INPUT) {
      const result = await (async () => {
        const engine = engines[modelName];
        return await engine.run({
          args: [question, enhancedText],
          options: {
            max_new_tokens: 1048576,
          },
        });
      })();
      questionInputResults.set(modelName, result);
    }

    // TODO: Fill mask
    */
    
  } catch (err) {
    results.push({error: err.message});
  }

  return results;
}

browser.runtime.onMessage.addListener((data, _, sendResponse) => {
  if (data.action !== "runAsyncTask") {
    sendResponse({ status: "error", error: "Unknown action"});
    return true;
  }

  useModels().then(results => {
    sendResponse({ status: "success", data: results });
  })
  .catch(err => {
      sendResponse({ status: "error", error: err });
  });

  // Return true to indicate an async sendResponse
  return true;
});
