const token = document.querySelector('meta[name="portale-token"]').content;
const $ = (selector) => document.querySelector(selector);
const list = $('#project-list');
let latest = null;
let toastTimer;

function icon(name) { return `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`; }
function toast(message, error = false) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.toggle('error', error);
  node.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove('visible'), 4200);
}
async function action(endpoint, data = {}) {
  const response = await fetch(`/api/${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Portale-Token': token }, body: JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Operazione non riuscita');
  return result;
}
async function refresh() {
  try {
    const response = await fetch('/api/status', { cache: 'no-store' });
    if (!response.ok) throw new Error('Stato non disponibile');
    latest = await response.json();
    render(latest);
  } catch (error) { toast(error.message, true); }
}
function render(state) {
  const installed = state.installed;
  const install = state.install;
  $('#setup').classList.toggle('ready', installed);
  $('#setup-title').textContent = installed ? 'OpenCode è pronto' : 'Installa OpenCode per iniziare';
  $('#install-detail').textContent = install.error || install.message || (installed ? 'Trovato su questo computer. Puoi avviare i tuoi progetti.' : 'Un clic scarica e verifica la release ufficiale per questo computer.');
  $('#install-button').hidden = installed;
  $('#install-button').disabled = install.busy;
  $('#install-button span').textContent = install.busy ? 'Installazione in corso…' : 'Installa OpenCode';
  $('#sidebar-dot').classList.toggle('ready', installed);
  $('#sidebar-status').textContent = installed ? 'OpenCode disponibile' : 'Installazione richiesta';
  $('#project-count').textContent = `${state.projects.length} ${state.projects.length === 1 ? 'progetto' : 'progetti'}`;
  list.replaceChildren();
  if (!state.projects.length) {
    const empty = document.createElement('div');
    empty.className = 'empty glass';
    empty.innerHTML = `${icon('folder')}<h3>Nessun progetto ancora</h3><p>Inserisci il percorso di una cartella per iniziare.</p>`;
    list.append(empty);
    return;
  }
  for (const project of state.projects) {
    const row = document.createElement('article');
    row.className = 'project glass';
    const main = document.createElement('div'); main.className = 'project-main';
    const symbol = document.createElement('span'); symbol.className = 'project-icon'; symbol.innerHTML = icon('folder');
    const details = document.createElement('div'); details.className = 'project-details';
    const name = document.createElement('h3'); name.textContent = project.name;
    const path = document.createElement('p'); path.textContent = project.path; path.title = project.path;
    details.append(name, path); main.append(symbol, details);
    const controls = document.createElement('div'); controls.className = 'project-controls';
    const stateBadge = document.createElement('span'); stateBadge.className = 'project-state' + (project.running ? ' active' : ''); stateBadge.textContent = project.running ? 'In esecuzione' : 'Pronto';
    const primary = document.createElement('button'); primary.type = 'button'; primary.className = 'button ' + (project.running ? 'button-secondary' : 'button-primary');
    primary.innerHTML = project.running ? `${icon('external')}<span>Apri</span>` : `${icon('arrow')}<span>Avvia OpenCode</span>`;
    primary.disabled = !installed;
    primary.addEventListener('click', async () => {
      const tab = window.open('about:blank', '_blank');
      if (tab) tab.opener = null;
      try { const result = await action('start', { path: project.path }); if (tab) tab.location.href = result.url; else window.location.href = result.url; await refresh(); toast('OpenCode avviato'); }
      catch (error) { if (tab) tab.close(); toast(error.message, true); }
    });
    const stop = document.createElement('button'); stop.type = 'button'; stop.className = 'icon-button danger'; stop.title = 'Arresta OpenCode'; stop.setAttribute('aria-label', `Arresta OpenCode per ${project.name}`); stop.innerHTML = icon('stop'); stop.hidden = !project.running;
    stop.addEventListener('click', async () => { try { await action('stop', { path: project.path }); await refresh(); toast('OpenCode arrestato'); } catch (error) { toast(error.message, true); } });
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'icon-button muted'; remove.title = 'Rimuovi dalla lista'; remove.setAttribute('aria-label', `Rimuovi ${project.name} dalla lista`); remove.innerHTML = icon('trash'); remove.hidden = project.running;
    remove.addEventListener('click', async () => { try { await action('remove', { path: project.path }); await refresh(); toast('Progetto rimosso dalla lista'); } catch (error) { toast(error.message, true); } });
    controls.append(stateBadge, primary, stop, remove); row.append(main, controls); list.append(row);
  }
}
$('#add-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const input = $('#project-path');
  try { await action('add', { path: input.value }); input.value = ''; await refresh(); toast('Progetto aggiunto'); }
  catch (error) { toast(error.message, true); input.focus(); }
});
$('#install-button').addEventListener('click', async () => { try { await action('install'); await refresh(); } catch (error) { toast(error.message, true); } });
const storedTheme = localStorage.getItem('portale-theme');
if (storedTheme === 'light' || storedTheme === 'dark') document.documentElement.dataset.theme = storedTheme;
function updateThemeButton() { const dark = document.documentElement.dataset.theme === 'dark' || (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches); $('#theme-button use').setAttribute('href', dark ? '#i-sun' : '#i-moon'); $('#theme-button').setAttribute('aria-label', dark ? 'Passa al tema chiaro' : 'Passa al tema scuro'); }
$('#theme-button').addEventListener('click', () => { const next = $('#theme-button use').getAttribute('href') === '#i-sun' ? 'light' : 'dark'; document.documentElement.dataset.theme = next; localStorage.setItem('portale-theme', next); updateThemeButton(); });
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateThemeButton);
updateThemeButton(); refresh(); setInterval(() => { if (!document.hidden) refresh(); }, 3000);
