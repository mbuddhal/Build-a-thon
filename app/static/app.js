const taskList = document.querySelector('#task-list');
const form = document.querySelector('#planner-form');
const resultPanel = document.querySelector('#result-panel');
const formError = document.querySelector('#form-error');
const modeBadge = document.querySelector('#mode-badge');
const template = document.querySelector('#task-row-template');
let currentPlan = null;
let baselinePlan = null;

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

function clonePlan(plan) {
  return JSON.parse(JSON.stringify(plan));
}

function sessionStepMarkup(step, index) {
  return `<li class="plan-node" draggable="true" data-step-index="${index}">
    <span class="drag-handle" aria-hidden="true">⋮⋮</span>
    <span class="step-number">${index + 1}</span>
    <label class="step-editor"><span class="sr-only">Step ${index + 1} name</span><input class="step-title-input" type="text" value="${escapeHtml(step.title)}" /></label>
    <label class="step-time-editor"><span class="sr-only">Step ${index + 1} minutes</span><input class="step-minutes-input" type="number" min="1" value="${Number(step.minutes) || 1}" /><span>min</span></label>
    <span class="step-move-controls"><button type="button" class="move-step" data-direction="up" aria-label="Move step ${index + 1} up" ${index === 0 ? 'disabled' : ''}>↑</button><button type="button" class="move-step" data-direction="down" aria-label="Move step ${index + 1} down" ${index === (currentPlan.session_steps.length - 1) ? 'disabled' : ''}>↓</button></span>
  </li>`;
}

function queueMarkup(task, index) {
  const previewSteps = (task.next_steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join('');
  return `<li class="queue-card"><div class="queue-card-heading"><span class="queue-number">${index + 1}</span><strong>${escapeHtml(task.name)}</strong></div><div class="queue-meta">Due: ${escapeHtml(task.due_date)} <span>·</span> Effort: ${escapeHtml(task.effort)} <span>·</span> Importance: ${escapeHtml(task.importance)}</div><details class="queue-details"><summary>AI preview of next moves</summary><ol>${previewSteps || '<li>Open the instructions and identify the first concrete deliverable.</li>'}</ol></details></li>`;
}

function readSessionEdits() {
  return [...document.querySelectorAll('#session-steps .plan-node')].map((node, index) => ({
    title: node.querySelector('.step-title-input').value.trim() || `Make progress on ${currentPlan.recommended_task.name}`,
    minutes: Math.max(1, Number(node.querySelector('.step-minutes-input').value) || 1),
    order: index + 1,
  }));
}

function saveSessionEdits() {
  const steps = readSessionEdits();
  const available = Number(document.querySelector('#available-minutes').value) || 0;
  const total = steps.reduce((sum, step) => sum + step.minutes, 0);
  const status = document.querySelector('#edit-status');
  if (total > available) {
    status.textContent = `Trim ${total - available} min to fit this session.`;
    status.className = 'edit-status edit-error';
    return;
  }
  currentPlan.session_steps = steps;
  currentPlan.total_minutes = total;
  renderPlan(currentPlan, false);
}

function reorderSessionSteps(index, direction) {
  currentPlan.session_steps = readSessionEdits();
  const nextIndex = direction === 'up' ? index - 1 : index + 1;
  if (nextIndex < 0 || nextIndex >= currentPlan.session_steps.length) return;
  [currentPlan.session_steps[index], currentPlan.session_steps[nextIndex]] = [currentPlan.session_steps[nextIndex], currentPlan.session_steps[index]];
  currentPlan.session_steps.forEach((step, stepIndex) => { step.order = stepIndex + 1; });
  renderPlan(currentPlan, false);
}

function wireSessionEditor() {
  const list = document.querySelector('#session-steps');
  if (!list) return;
  list.addEventListener('click', (event) => {
    const button = event.target.closest('.move-step');
    if (button) reorderSessionSteps(Number(button.closest('.plan-node').dataset.stepIndex), button.dataset.direction);
  });
  list.addEventListener('dragstart', (event) => {
    const node = event.target.closest('.plan-node');
    if (!node) return;
    currentPlan.session_steps = readSessionEdits();
    list.dataset.dragIndex = node.dataset.stepIndex;
    node.classList.add('dragging');
  });
  list.addEventListener('dragend', (event) => event.target.closest('.plan-node')?.classList.remove('dragging'));
  list.addEventListener('dragover', (event) => event.preventDefault());
  list.addEventListener('drop', (event) => {
    event.preventDefault();
    const target = event.target.closest('.plan-node');
    const from = Number(list.dataset.dragIndex);
    const to = Number(target?.dataset.stepIndex);
    if (!Number.isInteger(from) || !Number.isInteger(to) || from === to) return;
    const [moved] = currentPlan.session_steps.splice(from, 1);
    currentPlan.session_steps.splice(to, 0, moved);
    currentPlan.session_steps.forEach((step, index) => { step.order = index + 1; });
    renderPlan(currentPlan, false);
  });
}

function renderPlan(plan, resetBaseline = true) {
  currentPlan = clonePlan(plan);
  if (resetBaseline) baselinePlan = clonePlan(plan);
  const steps = currentPlan.session_steps.map(sessionStepMarkup).join('');
  const queue = currentPlan.queue.length ? currentPlan.queue.map(queueMarkup).join('') : '<li class="queue-empty">Nothing else is waiting in the queue.</li>';
  const uncertainties = currentPlan.uncertainties.length ? `<div class="uncertainties"><strong>Keep in mind</strong><ul>${currentPlan.uncertainties.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>` : '';
  const source = currentPlan.mode === 'live' ? `Live ${currentPlan.provider === 'anthropic' ? 'Claude' : 'OpenAI'} plan` : 'Demo plan';
  resultPanel.className = 'card result-card result-ready';
  resultPanel.innerHTML = `<div class="result-header"><div><p class="eyebrow">${source}</p><h2>Start with ${escapeHtml(currentPlan.recommended_task.name)}</h2></div><span class="time-pill">${currentPlan.total_minutes} / ${document.querySelector('#available-minutes').value} min</span></div><p class="summary">${escapeHtml(currentPlan.summary)}</p><div class="result-section session-section"><div class="result-section-title"><span class="section-dot accent"></span><h3>Session plan</h3><span class="edit-hint">Drag steps or use ↑ ↓</span></div><p class="section-help">These are the next moves for this study block. Edit the wording, time, or order to match how you work.</p><ol id="session-steps" class="steps-list">${steps}</ol><div class="session-actions"><button id="save-plan" class="button button-primary" type="button">Save edits</button><button id="reset-plan" class="button button-secondary" type="button">Reset AI plan</button><span id="edit-status" class="edit-status" role="status"></span></div></div><div class="result-section queue-section"><div class="result-section-title"><span class="section-dot queue"></span><h3>Later queue</h3><span class="queue-caption">${currentPlan.queue.length} assignment${currentPlan.queue.length === 1 ? '' : 's'} waiting</span></div><p class="section-help">Everything else stays here with a quick AI preview and the details you supplied.</p><ol class="queue-list">${queue}</ol></div>${uncertainties}<button id="edit-inputs" class="button button-secondary" type="button">Edit workload inputs</button>`;
  document.querySelector('#save-plan').addEventListener('click', saveSessionEdits);
  document.querySelector('#reset-plan').addEventListener('click', () => renderPlan(baselinePlan));
  document.querySelector('#edit-inputs').addEventListener('click', () => document.querySelector('#available-minutes').focus());
  wireSessionEditor();
}

async function refreshHealth() {
  try {
    const response = await fetch('/api/health');
    const health = await response.json();
    modeBadge.textContent = health.mode === 'live' ? `Live · ${health.provider === 'anthropic' ? 'Claude' : 'OpenAI'} · ${health.model}` : 'Demo mode · no live provider';
    modeBadge.className = `status-badge ${health.mode}`;
  } catch {
    modeBadge.textContent = 'Planner offline'; modeBadge.className = 'status-badge error';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault(); formError.textContent = '';
  const payload = { available_minutes: Number(document.querySelector('#available-minutes').value), tasks: collectTasks() };
  if (!payload.tasks.length) { formError.textContent = 'Add at least one assignment with a name.'; return; }
  resultPanel.className = 'card result-card loading-state'; resultPanel.innerHTML = '<div class="loading-orb"></div><p class="eyebrow">Working</p><h2>Untangling the actual task…</h2><p>The planner is choosing task-specific study moves, then checking the time budget.</p>';
  try {
    const response = await fetch('/api/plan', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'The planner could not complete this run.');
    renderPlan(body);
  } catch (error) {
    resultPanel.className = 'card result-card error-state'; resultPanel.innerHTML = `<p class="eyebrow">Needs attention</p><h2>The plan could not be completed.</h2><p>${escapeHtml(error.message)}</p><button id="retry-plan" class="button button-secondary" type="button">Try again</button>`;
    document.querySelector('#retry-plan').addEventListener('click', () => form.requestSubmit());
  }
});

document.querySelector('#add-task-button').addEventListener('click', () => addTask());
document.querySelector('#example-button').addEventListener('click', async () => { const response = await fetch('/api/fixture'); const fixture = await response.json(); loadExample(fixture.tasks, fixture.available_minutes); });
addTask(); refreshHealth();
