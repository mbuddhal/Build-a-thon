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

function scheduleBlockMarkup(block, index) {
  const steps = (block.steps || []).map((step, stepIndex) => `<li><span class="step-number">${stepIndex + 1}</span><label class="schedule-step-editor"><span class="sr-only">${escapeHtml(block.task.name)} step ${stepIndex + 1}</span><input class="schedule-step-input" type="text" value="${escapeHtml(step.title)}" /></label></li>`).join('');
  return `<li class="schedule-block" data-schedule-index="${index}"><div class="schedule-block-header"><span class="drag-handle" aria-label="Drag to reorder" role="button" tabindex="0">⋮⋮</span><span class="step-number">${index + 1}</span><div class="schedule-task-title"><strong>${escapeHtml(block.task.name)}</strong><small>Due: ${escapeHtml(block.task.due_date)} · Effort: ${escapeHtml(block.task.effort)} · Importance: ${escapeHtml(block.task.importance)}</small></div><label class="block-time-editor"><span class="sr-only">Minutes for ${escapeHtml(block.task.name)}</span><input class="block-minutes-input" type="number" min="1" value="${Number(block.minutes) || 1}" /><span>min</span></label></div><ol class="schedule-substeps">${steps}</ol></li>`;
}

function queueMarkup(task, index) {
  const previewSteps = (task.next_steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join('');
  return `<li class="queue-card"><div class="queue-card-heading"><span class="queue-number">${index + 1}</span><strong>${escapeHtml(task.name)}</strong></div><div class="queue-meta">Due: ${escapeHtml(task.due_date)} <span>·</span> Effort: ${escapeHtml(task.effort)} <span>·</span> Importance: ${escapeHtml(task.importance)}</div><details class="queue-details"><summary>AI preview of next moves</summary><ol>${previewSteps || '<li>Open the instructions and identify the first concrete deliverable.</li>'}</ol></details></li>`;
}

function readScheduleEdits() {
  return [...document.querySelectorAll('#study-schedule .schedule-block')].map((node) => {
    const original = currentPlan.schedule[Number(node.dataset.scheduleIndex)];
    return {
      task: original.task,
      task_id: original.task.id,
      minutes: Math.max(1, Number(node.querySelector('.block-minutes-input').value) || 1),
      steps: [...node.querySelectorAll('.schedule-step-input')].map((input) => ({title: input.value.trim() || 'Continue the next concrete piece', minutes: 1})),
    };
  });
}

function saveScheduleEdits() {
  const schedule = readScheduleEdits();
  const available = Number(document.querySelector('#available-minutes').value) || 0;
  const total = schedule.reduce((sum, block) => sum + block.minutes, 0);
  const status = document.querySelector('#edit-status');
  if (total > available) {
    status.textContent = `Trim ${total - available} min to fit this session.`;
    status.className = 'edit-status edit-error';
    return;
  }
  currentPlan.schedule = schedule;
  currentPlan.total_minutes = total;
  currentPlan.unused_minutes = Math.max(0, available - total);
  renderPlan(currentPlan, false);
}

function wireScheduleEditor() {
  const list = document.querySelector('#study-schedule');
  if (!list) return;
  let draggedNode = null;
  let draggedPointerId = null;
  let dragStartX = 0;
  let dragStartY = 0;
  let didPointerMove = false;

  const finishPointerDrag = (event) => {
    if (!draggedNode || (event && event.pointerId !== draggedPointerId)) return;
    const node = draggedNode;
    node.classList.remove('dragging');
    if (node.hasPointerCapture?.(draggedPointerId)) node.releasePointerCapture(draggedPointerId);
    draggedNode = null;
    draggedPointerId = null;
    if (didPointerMove) {
      currentPlan.schedule = readScheduleEdits();
      renderPlan(currentPlan, false);
    }
    didPointerMove = false;
  };

  list.addEventListener('pointerdown', (event) => {
    const node = event.target.closest('.schedule-block');
    if (event.target.closest('input, textarea, select, button, a')) return;
    if (!node) return;
    event.preventDefault();
    currentPlan.schedule = readScheduleEdits();
    draggedNode = node;
    draggedPointerId = event.pointerId;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    didPointerMove = false;
    node.classList.add('dragging');
    node.setPointerCapture?.(event.pointerId);
  });

  list.addEventListener('pointermove', (event) => {
    if (!draggedNode || event.pointerId !== draggedPointerId) return;
    event.preventDefault();
    if (Math.hypot(event.clientX - dragStartX, event.clientY - dragStartY) < 4) return;
    didPointerMove = true;
    const otherNodes = [...list.querySelectorAll('.schedule-block')].filter((node) => node !== draggedNode);
    const target = otherNodes.find((node) => event.clientY < node.getBoundingClientRect().top + node.getBoundingClientRect().height / 2);
    if (target) list.insertBefore(draggedNode, target);
    else if (otherNodes.length) list.appendChild(draggedNode);
  });

  list.addEventListener('pointerup', finishPointerDrag);
  list.addEventListener('pointercancel', finishPointerDrag);
}

function renderPlan(plan, resetBaseline = true) {
  currentPlan = clonePlan(plan);
  if (resetBaseline) baselinePlan = clonePlan(plan);
  const schedule = currentPlan.schedule.length ? currentPlan.schedule.map(scheduleBlockMarkup).join('') : '<li class="queue-empty">No assignment could fit this session.</li>';
  const queue = currentPlan.queue.length ? currentPlan.queue.map(queueMarkup).join('') : '<li class="queue-empty">Everything fits into this study block.</li>';
  const uncertainties = currentPlan.uncertainties.length ? `<div class="uncertainties"><strong>Keep in mind</strong><ul>${currentPlan.uncertainties.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>` : '';
  const source = currentPlan.mode === 'live' ? `Live ${currentPlan.provider === 'anthropic' ? 'Claude' : 'OpenAI'} schedule` : 'Demo schedule';
  const unused = currentPlan.unused_minutes ? `<span class="unused-time">${currentPlan.unused_minutes} min flexible time</span>` : '';
  const availableMinutes = document.querySelector('#available-minutes').value;
  const workloadNote = currentPlan.overage_minutes > 0
    ? `<p class="workload-note over-budget"><strong>Estimated workload: ${currentPlan.estimated_total_minutes} min.</strong> That is ${currentPlan.overage_minutes} min over this ${availableMinutes}-minute session.</p>`
    : `<p class="workload-note"><strong>Estimated workload: ${currentPlan.estimated_total_minutes} min.</strong> This session has enough time for the current estimates.</p>`;
  const nextSession = currentPlan.next_session_task
    ? `<div class="next-session-callout"><p class="eyebrow">Next study session</p><strong>Start with ${escapeHtml(currentPlan.next_session_task.name)}</strong><p>It is the highest-priority task with work left after today.</p></div>`
    : `<div class="next-session-callout next-session-clear"><p class="eyebrow">Next study session</p><strong>Nothing is waiting.</strong><p>Every assignment fit into this session.</p></div>`;
  resultPanel.className = 'card result-card result-ready';
  resultPanel.innerHTML = `<div class="result-header"><div><p class="eyebrow">${source}</p><h2>Your study schedule</h2></div><span class="time-pill">${currentPlan.total_minutes} / ${availableMinutes} min</span></div><p class="summary">${escapeHtml(currentPlan.summary)}</p>${workloadNote}<div class="result-section session-section"><div class="result-section-title"><span class="section-dot accent"></span><h3>Session schedule</h3><span class="edit-hint">${unused || 'All available time allocated'} · drag blocks to reorder</span></div><p class="section-help">Time is divided across assignments by priority. Drag a block to change the order, or edit its minutes and next steps.</p><ol id="study-schedule" class="schedule-list">${schedule}</ol><div class="session-actions"><button id="save-plan" class="button button-primary" type="button">Save edits</button><button id="reset-plan" class="button button-secondary" type="button">Reset AI schedule</button><span id="edit-status" class="edit-status" role="status"></span></div></div><div class="result-section queue-section"><div class="result-section-title"><span class="section-dot queue"></span><h3>Later queue</h3><span class="queue-caption">${currentPlan.queue.length} assignment${currentPlan.queue.length === 1 ? '' : 's'} waiting</span></div><p class="section-help">Assignments that did not fit this session, with their supplied details and a preview of what to do next.</p><ol class="queue-list">${queue}</ol></div>${nextSession}${uncertainties}<button id="edit-inputs" class="button button-secondary" type="button">Edit workload inputs</button>`;
  document.querySelector('#save-plan').addEventListener('click', saveScheduleEdits);
  document.querySelector('#reset-plan').addEventListener('click', () => renderPlan(baselinePlan));
  document.querySelector('#edit-inputs').addEventListener('click', () => document.querySelector('#available-minutes').focus());
  wireScheduleEditor();
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
  resultPanel.className = 'card result-card loading-state'; resultPanel.innerHTML = '<div class="loading-orb"></div><p class="eyebrow">Working</p><h2>Building your study schedule…</h2><p>The planner is ranking assignments, dividing the time, and choosing task-specific study moves.</p>';
  try {
    const response = await fetch('/api/plan', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'The planner could not complete this run.');
    renderPlan(body);
  } catch (error) {
    resultPanel.className = 'card result-card error-state'; resultPanel.innerHTML = `<p class="eyebrow">Needs attention</p><h2>The schedule could not be completed.</h2><p>${escapeHtml(error.message)}</p><button id="retry-plan" class="button button-secondary" type="button">Try again</button>`;
    document.querySelector('#retry-plan').addEventListener('click', () => form.requestSubmit());
  }
});

document.querySelector('#add-task-button').addEventListener('click', () => addTask());
document.querySelector('#example-button').addEventListener('click', async () => { const response = await fetch('/api/fixture'); const fixture = await response.json(); loadExample(fixture.tasks, fixture.available_minutes); });
addTask(); refreshHealth();
