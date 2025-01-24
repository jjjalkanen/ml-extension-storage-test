/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */


const taskToModel = {
  /**
   * Some of the models are base models like vit-base-patch16-224
   * and the output does not contain "logits" for classification,
   * we need to use a model which is fine-tuned for some set of classes,
   * such as cifar10.
   */
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
};

function getOpts(aName) {
  // If modelRevision "main" is not specified, there's a problem with default in
  // Error: Could not locate file:
  // "https://model-hub.mozilla.org/Xenova/vit-base-patch16-224/default/preprocessor_config.json".
  if (!(aName in taskToModel)) {
    return { taskName: aName, modelRevision: "main" };
  }

  return taskToModel[aName];
}

function finalize(aPort, results) {
  // Define the target URL (the page where we want to set localStorage)
  const targetUrl = "https://*.example.org/*";
  const extensionId = browser.runtime.id;
  const value = JSON.stringify(results);

  aPort.postMessage({
    type: "progressUpdate",
    progress: `Finalizing ${extensionId}`,
  });

  // Use tabs API to inject a script into the page
  browser.tabs.query({ url: targetUrl }).then(tabs => {
    if (tabs.length > 0) {
      // Inject a content script into the page to set localStorage
      const code_snippet = `window.localStorage.setItem('${extensionId}', '${value}');`;
      aPort.postMessage({
        type: "progressUpdate",
        progress: code_snippet,
      });
      browser.tabs.executeScript(tabs[0].id, {
        code: code_snippet
      });
    }
  }).catch(err => {
    const code_snippet = `window.localStorage.setItem('${extensionId}', '${err.message}');`;
    aPort.postMessage({
      type: "progressUpdate",
      progress: code_snippet,
    });
    browser.tabs.executeScript(tabs[0].id, {
      code: code_snippet
    });
  });
}

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

let firstRun = true;
let results = [];
let what = "success";
async function useModels(aPort, taskName) {
  const listener = progressData => {
    aPort.postMessage({
      type: "progressUpdate",
      progress: progressData,
    });
  };

  browser.trial.ml.onProgress.addListener(listener);

  aPort.postMessage({
    type: "progressUpdate",
    progress: "Starting " + taskName,
  });

  try {
    if (firstRun) {

      await new Promise((resolve, reject) => {
          aPort.postMessage({
            type: "progressUpdate",
            progress: "Loading " + taskName,
          });
          try {
            const opts = getOpts(taskName);
            const start = performance.now();
            browser.trial.ml.createEngine(opts).then(() => {
              results.push({
                name: taskName,
                took: performance.now() - start,
              });
              resolve();
            }).catch(err => {
              results.push({
                name: taskName,
                error: err.message
              });
              reject();
            });
          } catch (err) {
            results.push({
              name: taskName,
              error: err.message
            });
            reject();
          } finally {
            firstRun = false;
          }
        });

      aPort.postMessage({
        type: "progressUpdate",
        progress: "Model loading done!",
      });
      firstRun = false;
    }

  /*
    const jpegDataUrl = createImageSample();

    const WITH_IMAGE_INPUT = {
      "zero-shot-image-classification": {
        args: [
          "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg",
          ["animals", "nature"]
        ],
      },
      "zero-shot-object-detection": {
        args: [
          "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg",
          ["tiger"]
        ],
      },
      "image-to-text": {
        args: [
          jpegDataUrl 
        ],
        options: {
          max_new_tokens: 300,
        }
      },
    };

    function getArgs(aName) {
      // Sometimes special arguments are needed
      if (!(aName in WITH_IMAGE_INPUT)) {
        return {
          args: [
            "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/tiger.jpg"
          ]
        };
      }
    
      return WITH_IMAGE_INPUT[aName];
    }

    for (const modelName of Object.keys(WITH_IMAGE_INPUT)) {
      aPort.postMessage({
        type: "progressUpdate",
        progress: "Running " + modelName,
      });
      const args = getArgs(modelName);
      const start = performance.now();
      const result = await browser.trial.ml.runEngine(args);
      results.push({name: modelName, took: performance.now() - start});
    }

    aPort.postMessage({
      type: "progressUpdate",
      progress: "Image model running done!"
    });

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
    what = "error";
    aPort.postMessage({
      type: "progressUpdate",
      progress: err.message,
    });
  } finally {
    finalize(aPort, results);
  }
}

let isRunning = false;

browser.runtime.onConnect.addListener((port) => {
  if (port.name.startsWith("progressChannel")) {
    const portNameParts = port.name.split(".");
    if (portNameParts.length < 2) {
      finalize(port, ["Improper port name"]);

      return true;
    }
    const taskName = portNameParts.pop();

    port.onMessage.addListener((msg) => {
      if (msg.taskName !== taskName) {
        return true;
      }

      if (msg.action !== "runAsyncTask") {
        finalize(port, ["Unknown action"]);

        return true;
      }

      if (isRunning) {
        port.postMessage({
          type: "progressUpdate",
          progress: "Already in progress",
        });

        return true;
      }

      useModels(port, taskName);
      isRunning = true;

      return true;
    });
  }
});
