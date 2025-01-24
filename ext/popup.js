let port = null;

function makeRow(rowContents) {
  const row = document.createElement("tr");
  rowContents.forEach(elem => {
    const cell = document.createElement("td");
    cell.textContent = JSON.stringify(elem);
    row.appendChild(cell);
  });
  return row;
}

document.addEventListener("DOMContentLoaded", () => {
  const startButton = document.getElementById("startButton");
  const statusField = document.getElementById("status");
  const resultsDiv = document.getElementById("results");
  const progressTable = document.getElementById("progress");

  const params = new URLSearchParams(window.location.search);
  const taskName = params.get('taskName');
  {
    const row = makeRow([taskName]);
    progressTable.appendChild(row);
  }

  // Connect to background when popup loads
  port = browser.runtime.connect({ name: "progressChannel." + taskName });

  // Listen for messages from background
  port.onMessage.addListener((msg) => {
    if (msg.type === "progressUpdate") {
      const row = makeRow([msg.progress]);
      progressTable.appendChild(row);
    } else if (msg.type === "progressComplete") {
      const response = msg.results;
      statusField.innerText = response.what;
      const table = document.createElement("table");
      const results = JSON.parse(response.data);
      const row = makeRow(results);
      table.appendChild(row);
      resultsDiv.appendChild(table);
    }
  });

  startButton.addEventListener("click", () => {
    // Reset UI
    statusField.textContent = "";
    resultsDiv.innerHTML = "";

    // Send message to background
    port.postMessage({ action: "runAsyncTask", taskName });
  });
});