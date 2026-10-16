const taskList = document.querySelector('#task-list');
const form = document.querySelector('#planner-form');
const resultPanel = document.querySelector('#result-panel');
const formError = document.querySelector('#form-error');
const modeBadge = document.querySelector('#mode-badge');
const template = document.querySelector('#task-row-template');

function addTask(task = {}) {
  const row = template.content.firstElementChild.cloneNode(true);
  row.querySelector('.task-name').value = task.name || '';
  row.querySelector('.task-due').value = task.due_date && task.due_date !== 'N/A' ? task.due_date : '';
  row.querySelector('.task-effort').value = task.effort && task.effort !== 'N/A' ? task.effort : '';
  row.querySelector('.task-importance').value = task.importance || 'N/A';
  row.querySelector('.task-dependencies').value = task.dependencies && task.dependencies !== 'N/A' ? task.dependencies : '';
  row.querySelector('.remove-task').addEventListener('click', () => { row.remove(); if (!taskList.children.length) addTask(); });
  taskList.appendChild(row);
}

function loadExample(tasks, minutes = 45) {
  taskList.replaceChildren(); tasks.forEach(addTask); document.querySelector('#available-minutes').value = minutes;
}

function collectTasks() {
  return [...taskList.querySelectorAll('.task-row')].map((row) => ({
    name: row.querySelector('.task-name').value.trim(),
    due_date: row.querySelector('.task-due').value || 'N/A',
    effort: row.querySelector('.task-effort').value.trim() || 'N/A',
    importance: row.querySelector('.task-importance').value || 'N/A',
    dependencies: row.querySelector('.task-dependencies').value.trim() || 'N/A',
  })).filter((task) => task.name);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function renderPlan(plan) {
  const steps = plan.session_steps.map((step) => `<li><span class="step-number">${step.order}</span><span>${escapeHtml(step.title)}</span><strong>${step.minutes} min</strong></li>`).join('');
  const queue = plan.queue.length ? plan.queue.map((task, index) => `<li><span class="queue-number">${index + 1}</span><div><strong>${escapeHtml(task.name)}</strong><small>Due: ${escapeHtml(task.due_date)} · Effort: ${escapeHtml(task.effort)} · Importance: ${escapeHtml(task.importance)}</small></div></li>`).join('') : '<li class="queue-empty">Nothing else is waiting in the queue.</li>';
  const uncertainties = plan.uncertainties.length ? `<div class="uncertainties"><strong>Keep in mind</strong><ul>${plan.uncertainties.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>` : '';
  resultPanel.className = 'card result-card result-ready';
  resultPanel.innerHTML = `<div class="result-header"><div><p class="eyebrow">${plan.mode === 'live' ? 'Live AI plan' : 'Demo plan'}</p><h2>Start with ${escapeHtml(plan.recommended_task.name)}</h2></div><span class="time-pill">${plan.total_minutes} / ${document.querySelector('#available-minutes').value} min</span></div><p class="summary">${escapeHtml(plan.summary)}</p><div class="result-section"><div class="result-section-title"><span class="section-dot accent"></span><h3>Your session plan</h3></div><ol class="steps-list">${steps}</ol></div><div class="result-section queue-section"><div class="result-section-title"><span class="section-dot queue"></span><h3>Later queue</h3><span class="queue-caption">${plan.queue.length} assignment${plan.queue.length === 1 ? '' : 's'} waiting</span></div><ol class="queue-list">${queue}</ol></div>${uncertainties}<button id="edit-plan" class="button button-secondary">Edit inputs and run again</button>`;
  document.querySelector('#edit-plan').addEventListener('click', () => document.querySelector('#available-minutes').focus());
}

async function refreshHealth() {
  try { const response = await fetch('/api/health'); const health = await response.json(); modeBadge.textContent = health.mode === 'live' ? `Live · ${health.model}` : 'Demo mode · API key not detected'; modeBadge.className = `status-badge ${health.mode}`; }
  catch { modeBadge.textContent = 'Planner offline'; modeBadge.className = 'status-badge error'; }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault(); formError.textContent = '';
  const payload = { available_minutes: Number(document.querySelector('#available-minutes').value), tasks: collectTasks() };
  if (!payload.tasks.length) { formError.textContent = 'Add at least one assignment with a name.'; return; }
  resultPanel.className = 'card result-card loading-state'; resultPanel.innerHTML = '<div class="loading-orb"></div><p class="eyebrow">Working</p><h2>Finding your next move…</h2><p>The planner is comparing urgency, effort, and dependencies, then checking the time budget.</p>';
  try { const response = await fetch('/api/plan', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}); const body = await response.json(); if (!response.ok) throw new Error(body.error || 'The planner could not complete this run.'); renderPlan(body); }
  catch (error) { resultPanel.className = 'card result-card error-state'; resultPanel.innerHTML = `<p class="eyebrow">Needs attention</p><h2>The plan could not be completed.</h2><p>${escapeHtml(error.message)}</p><button id="retry-plan" class="button button-secondary">Try again</button>`; document.querySelector('#retry-plan').addEventListener('click', () => form.requestSubmit()); }
});

document.querySelector('#add-task-button').addEventListener('click', () => addTask());
document.querySelector('#example-button').addEventListener('click', async () => { const response = await fetch('/api/fixture'); const fixture = await response.json(); loadExample(fixture.tasks, fixture.available_minutes); });
addTask(); refreshHealth();
