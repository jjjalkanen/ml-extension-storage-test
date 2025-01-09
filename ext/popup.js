document.addEventListener("DOMContentLoaded", () => {
  const startButton = document.getElementById("startButton");
  const statusField = document.getElementById("status");
  const resultsDiv = document.getElementById("results");

  startButton.addEventListener("click", () => {
    // Reset UI
    statusField.textContent = "";
    resultsDiv.innerHTML = "";

    // Send message to background
    browser.runtime.sendMessage({ action: "runAsyncTask" }).then(response => {
      if (response.status === "success") {
        statusField.textContent = "success";
        const table = document.createElement("table");
        const row = document.createElement("tr");
        response.data.forEach(num => {
          const cell = document.createElement("td");
          cell.textContent = JSON.stringify(num);
          row.appendChild(cell);
        });
        table.appendChild(row);
        resultsDiv.appendChild(table);

      } else if (response.status === "error") {
        statusField.textContent = "error";
        const errorDiv = document.createElement("div");
        errorDiv.textContent = response.error;
        resultsDiv.appendChild(errorDiv);
      }
    });
  });
});