async function resetEnv() {
  const res = await fetch('/reset', { method: 'POST' });
  const data = await res.json();
  render(data);
}

async function stepEnv() {
  const incident_id = document.getElementById("incident").value;
  const type = document.getElementById("action").value;

  const res = await fetch('/step', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, incident_id })
  });

  const data = await res.json();

  render(data.state);
  document.getElementById("reward").innerText = "Reward: " + data.reward;
  document.getElementById("done").innerText = "Done: " + data.done;
}

function render(state) {
  const table = document.getElementById("table");
  const dropdown = document.getElementById("incident");

  table.innerHTML = "<tr><th>ID</th><th>Severity</th><th>Service</th><th>Status</th></tr>";
  dropdown.innerHTML = "";

  state.incidents.forEach(inc => {
    table.innerHTML += `
      <tr>
        <td>${inc.id}</td>
        <td>${inc.severity}</td>
        <td>${inc.service}</td>
        <td>${inc.status}</td>
      </tr>
    `;

    dropdown.innerHTML += `<option value="${inc.id}">${inc.id}</option>`;
  });
}