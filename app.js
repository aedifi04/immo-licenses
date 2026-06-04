'use strict';

const App = {
  project: null,
  settings: null,
  editingItemId: null,
  currentCategory: null,

  // ── Init ──────────────────────────────────────────────────────────────────

  init() {
    this.settings = this.loadSettings();
    this.project = this.createProject();
    this.populateSettingsForm();
    this.populateProjectForm();
    this.renderItems();
    this.updateSummary();
    this.updateDocBadge();
  },

  // ── Settings ─────────────────────────────────────────────────────────────

  defaultSettings() {
    return {
      company: { name: '', address: '', email: '', phone: '', siret: '', tvaNumber: '', paymentTerms: 'Paiement à 30 jours.' },
      rates: { cad: 80, machining: 90, welding: 70, laser: 60, scan3d: 75, postProcessing: 60 },
      materials: {
        filamentPriceKg: 25,
        resinPriceL: 40,
        metalPowderPriceKg: 300,
        electricityKwh: 0.20,
        fdmPowerW: 200,
        metalPowerW: 2000,
      },
    };
  },

  loadSettings() {
    try {
      const s = localStorage.getItem('fabBilling_settings');
      if (s) return { ...this.defaultSettings(), ...JSON.parse(s) };
    } catch (_) {}
    return this.defaultSettings();
  },

  saveSettings() {
    const s = this.settings;
    s.company.name          = document.getElementById('s-companyName').value;
    s.company.address       = document.getElementById('s-companyAddress').value;
    s.company.email         = document.getElementById('s-companyEmail').value;
    s.company.phone         = document.getElementById('s-companyPhone').value;
    s.company.siret         = document.getElementById('s-companySiret').value;
    s.company.tvaNumber     = document.getElementById('s-companyTvaNum').value;
    s.company.paymentTerms  = document.getElementById('s-paymentTerms').value;
    s.rates.cad             = num('s-rateCAD', 80);
    s.rates.machining       = num('s-rateMachining', 90);
    s.rates.welding         = num('s-rateWelding', 70);
    s.rates.laser           = num('s-rateLaser', 60);
    s.rates.scan3d          = num('s-rateScan', 75);
    s.materials.filamentPriceKg    = num('s-filamentPrice', 25);
    s.materials.resinPriceL        = num('s-resinPrice', 40);
    s.materials.metalPowderPriceKg = num('s-metalPowderPrice', 300);
    s.materials.electricityKwh     = num('s-electricityPrice', 0.20);
    s.materials.fdmPowerW          = num('s-fdmPowerW', 200);
    s.materials.metalPowerW        = num('s-metalPowerW', 2000);
    localStorage.setItem('fabBilling_settings', JSON.stringify(s));
    this.showToast('Paramètres sauvegardés ✓');
  },

  populateSettingsForm() {
    const s = this.settings;
    set('s-companyName', s.company.name);
    set('s-companyAddress', s.company.address);
    set('s-companyEmail', s.company.email);
    set('s-companyPhone', s.company.phone);
    set('s-companySiret', s.company.siret);
    set('s-companyTvaNum', s.company.tvaNumber);
    set('s-paymentTerms', s.company.paymentTerms);
    set('s-rateCAD', s.rates.cad);
    set('s-rateMachining', s.rates.machining);
    set('s-rateWelding', s.rates.welding);
    set('s-rateLaser', s.rates.laser);
    set('s-rateScan', s.rates.scan3d);
    set('s-filamentPrice', s.materials.filamentPriceKg);
    set('s-resinPrice', s.materials.resinPriceL);
    set('s-metalPowderPrice', s.materials.metalPowderPriceKg);
    set('s-electricityPrice', s.materials.electricityKwh);
    set('s-fdmPowerW', s.materials.fdmPowerW);
    set('s-metalPowerW', s.materials.metalPowerW);
  },

  // ── Project lifecycle ─────────────────────────────────────────────────────

  createProject() {
    const today     = isoDate(new Date());
    const validUntil = isoDate(new Date(Date.now() + 30 * 86400000));
    return {
      id: Date.now().toString(),
      document: { type: 'devis', number: this.nextDocNumber('devis'), date: today, validUntil, dueDate: validUntil, projectName: '' },
      client:   { name: '', company: '', address: '', phone: '', email: '' },
      items:    [],
      options:  { tva: 20, discount: 0, notes: '' },
    };
  },

  nextDocNumber(type) {
    const year = new Date().getFullYear();
    const key  = `fabBilling_counter_${type}_${year}`;
    const n    = parseInt(localStorage.getItem(key) || '0') + 1;
    localStorage.setItem(key, String(n));
    return `${type === 'devis' ? 'DEV' : 'FAC'}-${year}-${String(n).padStart(3, '0')}`;
  },

  newProject() {
    if (!confirm('Créer un nouveau projet ? (le projet courant sera perdu si non sauvegardé)')) return;
    this.project = this.createProject();
    this.populateProjectForm();
    this.renderItems();
    this.updateSummary();
    this.updateDocBadge();
  },

  readProjectForm() {
    const p = this.project;
    p.document.type        = document.getElementById('docType').value;
    p.document.number      = document.getElementById('docNum').value;
    p.document.date        = document.getElementById('docDate').value;
    p.document.validUntil  = document.getElementById('docValidUntil').value;
    p.document.dueDate     = document.getElementById('docDueDate').value;
    p.document.projectName = document.getElementById('docProject').value;
    p.client.company       = document.getElementById('clientCompany').value;
    p.client.name          = document.getElementById('clientName').value;
    p.client.address       = document.getElementById('clientAddress').value;
    p.client.email         = document.getElementById('clientEmail').value;
    p.client.phone         = document.getElementById('clientPhone').value;
    p.options.tva          = num('tvaRate', 20);
    p.options.discount     = num('discount', 0);
    p.options.notes        = document.getElementById('docNotes').value;
  },

  populateProjectForm() {
    const p = this.project;
    set('docType', p.document.type);
    set('docNum', p.document.number);
    set('docDate', p.document.date);
    set('docValidUntil', p.document.validUntil);
    set('docDueDate', p.document.dueDate);
    set('docProject', p.document.projectName);
    set('clientCompany', p.client.company);
    set('clientName', p.client.name);
    set('clientAddress', p.client.address);
    set('clientEmail', p.client.email);
    set('clientPhone', p.client.phone);
    set('tvaRate', p.options.tva);
    set('discount', p.options.discount);
    set('docNotes', p.options.notes || '');
    this.onDocTypeChange();
  },

  onDocTypeChange() {
    const type = document.getElementById('docType').value;
    document.getElementById('row-validUntil').style.display = type === 'devis' ? '' : 'none';
    document.getElementById('row-dueDate').style.display    = type === 'facture' ? '' : 'none';
    this.updateDocBadge();
  },

  updateDocBadge() {
    const type = document.getElementById('docType')?.value || 'devis';
    const num  = document.getElementById('docNum')?.value || '';
    const badge = document.getElementById('docBadge');
    const numEl = document.getElementById('docNumber');
    if (badge) {
      badge.textContent = type === 'devis' ? 'DEVIS' : 'FACTURE';
      badge.className   = 'doc-badge' + (type === 'facture' ? ' facture' : '');
    }
    if (numEl) numEl.textContent = num;
  },

  // ── Persistence ────────────────────────────────────────────────────────────

  saveToStorage() {
    this.readProjectForm();
    const all = this.allProjects();
    all[this.project.id] = this.project;
    localStorage.setItem('fabBilling_projects', JSON.stringify(all));
    this.showToast('Projet sauvegardé ✓');
  },

  allProjects() {
    try { return JSON.parse(localStorage.getItem('fabBilling_projects') || '{}'); }
    catch (_) { return {}; }
  },

  loadFromStorage() {
    const all  = this.allProjects();
    const keys = Object.keys(all);
    if (!keys.length) { alert('Aucun projet sauvegardé.'); return; }

    if (keys.length === 1) {
      this.loadProject(all[keys[0]]);
      return;
    }

    const lines = keys.map((k, i) => {
      const p = all[k];
      const client = p.client.company || p.client.name || 'Sans client';
      return `${i + 1}. ${p.document.number}  —  ${client}`;
    }).join('\n');

    const choice = prompt(`Choisissez un projet à charger :\n\n${lines}\n\nEntrez le numéro :`);
    if (!choice) return;
    const idx = parseInt(choice) - 1;
    if (idx >= 0 && idx < keys.length) this.loadProject(all[keys[idx]]);
  },

  loadProject(p) {
    this.project = p;
    this.populateProjectForm();
    this.renderItems();
    this.updateSummary();
    this.showToast('Projet chargé ✓');
  },

  exportJSON() {
    this.readProjectForm();
    const blob = new Blob([JSON.stringify({ project: this.project, settings: this.settings }, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${this.project.document.number || 'projet'}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  },

  // ── Navigation ─────────────────────────────────────────────────────────────

  switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-btn-${tab}`).classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');
    if (tab === 'summary') this.updateSummary();
    this.updateDocBadge();
  },

  // ── Item calculations ──────────────────────────────────────────────────────

  itemTotal(item) {
    switch (item.category) {
      case 'cad':
        return (item.hours || 0) * (item.rate || 0);

      case 'print3d_plastic': {
        const filament = ((item.filamentG || 0) / 1000) * (item.filamentPriceKg || 0);
        const elec     = (item.printTimeH || 0) * ((item.printerW || 0) / 1000) * (item.elecPrice || 0);
        return filament + elec + (item.setupCost || 0);
      }

      case 'print3d_metal': {
        const powder = ((item.powderG || 0) / 1000) * (item.powderPriceKg || 0);
        const elec   = (item.printTimeH || 0) * ((item.printerW || 0) / 1000) * (item.elecPrice || 0);
        const post   = (item.postH || 0) * (item.postRate || 0);
        return powder + elec + post + (item.setupCost || 0);
      }

      case 'laser':
        return (item.machineH || 0) * (item.machineRate || 0) + (item.materialCost || 0);

      case 'machining':
        return (item.hours || 0) * (item.rate || 0) + (item.materialCost || 0);

      case 'welding':
        return (item.hours || 0) * (item.rate || 0) + (item.consumables || 0);

      case 'scan3d':
        return (item.hours || 0) * (item.rate || 0);

      case 'other':
        return (item.qty || 0) * (item.unitPrice || 0);

      default: return 0;
    }
  },

  itemDetails(item) {
    switch (item.category) {
      case 'cad':
        return `${item.hours}h × ${item.rate} €/h`;

      case 'print3d_plastic': {
        const f = ((item.filamentG || 0) / 1000) * (item.filamentPriceKg || 0);
        const e = (item.printTimeH || 0) * ((item.printerW || 0) / 1000) * (item.elecPrice || 0);
        return `${item.printTimeH}h · ${item.filamentG}g filament (${fmt(f)}) · élec. ${fmt(e)}` +
               (item.setupCost ? ` · setup ${fmt(item.setupCost)}` : '');
      }

      case 'print3d_metal': {
        const p = ((item.powderG || 0) / 1000) * (item.powderPriceKg || 0);
        const e = (item.printTimeH || 0) * ((item.printerW || 0) / 1000) * (item.elecPrice || 0);
        return `${item.printTimeH}h · ${item.powderG}g poudre (${fmt(p)}) · élec. ${fmt(e)}` +
               (item.postH ? ` · post-trait. ${item.postH}h` : '') +
               (item.setupCost ? ` · setup ${fmt(item.setupCost)}` : '');
      }

      case 'laser':
        return `${item.machineH}h × ${item.machineRate} €/h` +
               (item.materialCost ? ` + matière ${fmt(item.materialCost)}` : '');

      case 'machining':
        return `${item.hours}h × ${item.rate} €/h` +
               (item.materialCost ? ` + matière/outillage ${fmt(item.materialCost)}` : '');

      case 'welding':
        return `${item.hours}h × ${item.rate} €/h` +
               (item.consumables ? ` + consommables ${fmt(item.consumables)}` : '');

      case 'scan3d':
        return `${item.hours}h × ${item.rate} €/h`;

      case 'other':
        return `${item.qty} ${item.unit || 'u'} × ${fmt(item.unitPrice)}`;

      default: return '';
    }
  },

  // ── Item rendering ─────────────────────────────────────────────────────────

  catLabel(cat) {
    return { cad: 'CAD', print3d_plastic: 'Impression 3D', print3d_metal: 'Métal 3D',
             laser: 'Laser', machining: 'Usinage', welding: 'Soudage',
             scan3d: 'Scan 3D', other: 'Autre' }[cat] || cat;
  },

  catColor(cat) {
    return { cad: '#6366f1', print3d_plastic: '#10b981', print3d_metal: '#f59e0b',
             laser: '#ef4444', machining: '#3b82f6', welding: '#8b5cf6',
             scan3d: '#06b6d4', other: '#6b7280' }[cat] || '#6b7280';
  },

  renderItems() {
    const list  = document.getElementById('items-list');
    const empty = document.getElementById('items-empty');
    const items = this.project.items;

    if (!items.length) {
      list.innerHTML = '';
      empty.style.display = '';
      return;
    }
    empty.style.display = 'none';

    list.innerHTML = items.map((item) => {
      const total = this.itemTotal(item);
      const color = this.catColor(item.category);
      const id    = item.id;
      return `
        <div class="item-card" id="card-${id}">
          <span class="item-cat-badge" style="background:${color}">${this.catLabel(item.category)}</span>
          <div class="item-info">
            <div class="item-desc">${esc(item.desc || '(sans description)')}</div>
            <div class="item-details">${this.itemDetails(item)}</div>
          </div>
          <div class="item-total">${fmt(total)}</div>
          <div class="item-actions">
            <button class="btn btn-ghost btn-icon" title="Dupliquer" onclick="App.duplicateItem('${id}')">⧉</button>
            <button class="btn btn-ghost btn-icon" title="Modifier"  onclick="App.openItemModal('${item.category}','${id}')">✏️</button>
            <button class="btn btn-danger btn-icon" title="Supprimer" onclick="App.deleteItem('${id}')">🗑</button>
          </div>
        </div>`;
    }).join('');

    this.updateSummary();
  },

  deleteItem(id) {
    this.project.items = this.project.items.filter(i => i.id !== id);
    this.renderItems();
  },

  duplicateItem(id) {
    const src = this.project.items.find(i => i.id === id);
    if (!src) return;
    const copy = { ...src, id: Date.now().toString() };
    const idx = this.project.items.findIndex(i => i.id === id);
    this.project.items.splice(idx + 1, 0, copy);
    this.renderItems();
  },

  // ── Item modal ─────────────────────────────────────────────────────────────

  openItemModal(category, itemId = null) {
    this.currentCategory = category;
    this.editingItemId   = itemId || null;

    const item = itemId ? this.project.items.find(i => i.id === itemId) : null;

    document.getElementById('modal-title').textContent =
      `${itemId ? 'Modifier' : 'Ajouter'} — ${this.catLabel(category)}`;
    document.getElementById('modal-body').innerHTML = this.buildItemForm(category, item);
    document.getElementById('modal-overlay').classList.remove('hidden');

    this.refreshCostPreview();
    document.getElementById('modal-body').querySelectorAll('input, select').forEach(el => {
      el.addEventListener('input', () => this.refreshCostPreview());
    });
  },

  buildItemForm(cat, item) {
    const s = this.settings;
    const v = (k, def) => item != null ? (item[k] ?? def) : def;

    const descField = `
      <div class="field">
        <label>Description</label>
        <input type="text" id="f-desc" value="${esc(v('desc', ''))}" placeholder="Décrivez la prestation...">
      </div>`;

    switch (cat) {
      case 'cad': return descField + `
        <div class="field-row">
          <div class="field">
            <label>Heures de travail</label>
            <input type="number" id="f-hours" value="${v('hours', 0)}" min="0" step="0.25">
          </div>
          <div class="field">
            <label>Taux horaire (€/h)</label>
            <input type="number" id="f-rate" value="${v('rate', s.rates.cad)}" min="0" step="1">
          </div>
        </div>`;

      case 'print3d_plastic': return descField + `
        <div class="field-separator">Impression</div>
        <div class="field-row">
          <div class="field">
            <label>Durée impression (h)</label>
            <input type="number" id="f-printTimeH" value="${v('printTimeH', 0)}" min="0" step="0.1">
          </div>
          <div class="field">
            <label>Filament consommé (g)</label>
            <input type="number" id="f-filamentG" value="${v('filamentG', 0)}" min="0" step="1">
          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label>Prix filament (€/kg)</label>
            <input type="number" id="f-filamentPriceKg" value="${v('filamentPriceKg', s.materials.filamentPriceKg)}" min="0" step="0.5">
          </div>
          <div class="field">
            <label>Type de filament</label>
            <select id="f-filamentType">
              <option value="PLA"   ${v('filamentType','PLA') === 'PLA'    ? 'selected' : ''}>PLA</option>
              <option value="PETG"  ${v('filamentType','PLA') === 'PETG'   ? 'selected' : ''}>PETG</option>
              <option value="ABS"   ${v('filamentType','PLA') === 'ABS'    ? 'selected' : ''}>ABS</option>
              <option value="TPU"   ${v('filamentType','PLA') === 'TPU'    ? 'selected' : ''}>TPU</option>
              <option value="Nylon" ${v('filamentType','PLA') === 'Nylon'  ? 'selected' : ''}>Nylon</option>
              <option value="Résine"${v('filamentType','PLA') === 'Résine' ? 'selected' : ''}>Résine</option>
              <option value="Autre" ${v('filamentType','PLA') === 'Autre'  ? 'selected' : ''}>Autre</option>
            </select>
          </div>
        </div>
        <div class="field-separator">Électricité &amp; divers</div>
        <div class="field-row">
          <div class="field">
            <label>Puissance imprimante (W)</label>
            <input type="number" id="f-printerW" value="${v('printerW', s.materials.fdmPowerW)}" min="0" step="10">
          </div>
          <div class="field">
            <label>Prix électricité (€/kWh)</label>
            <input type="number" id="f-elecPrice" value="${v('elecPrice', s.materials.electricityKwh)}" min="0" step="0.01">
          </div>
        </div>
        <div class="field">
          <label>Coût setup / préparation (€)</label>
          <input type="number" id="f-setupCost" value="${v('setupCost', 0)}" min="0" step="0.5">
          <div class="field-hint">Temps de préparation fichier, nettoyage plateau, etc.</div>
        </div>`;

      case 'print3d_metal': return descField + `
        <div class="field-separator">Impression</div>
        <div class="field-row">
          <div class="field">
            <label>Durée impression (h)</label>
            <input type="number" id="f-printTimeH" value="${v('printTimeH', 0)}" min="0" step="0.1">
          </div>
          <div class="field">
            <label>Poudre métal consommée (g)</label>
            <input type="number" id="f-powderG" value="${v('powderG', 0)}" min="0" step="1">
          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label>Prix poudre (€/kg)</label>
            <input type="number" id="f-powderPriceKg" value="${v('powderPriceKg', s.materials.metalPowderPriceKg)}" min="0" step="1">
          </div>
          <div class="field">
            <label>Alliage</label>
            <input type="text" id="f-metalAlloy" value="${esc(v('metalAlloy', '316L'))}" placeholder="ex: 316L, Ti6Al4V, AlSi10Mg">
          </div>
        </div>
        <div class="field-separator">Électricité &amp; post-traitement</div>
        <div class="field-row">
          <div class="field">
            <label>Puissance imprimante (W)</label>
            <input type="number" id="f-printerW" value="${v('printerW', s.materials.metalPowerW)}" min="0" step="100">
          </div>
          <div class="field">
            <label>Prix électricité (€/kWh)</label>
            <input type="number" id="f-elecPrice" value="${v('elecPrice', s.materials.electricityKwh)}" min="0" step="0.01">
          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label>Post-traitement (h)</label>
            <input type="number" id="f-postH" value="${v('postH', 0)}" min="0" step="0.25">
            <div class="field-hint">Dépoudrage, HIP, usinage de finition...</div>
          </div>
          <div class="field">
            <label>Taux post-traitement (€/h)</label>
            <input type="number" id="f-postRate" value="${v('postRate', s.rates.postProcessing)}" min="0" step="1">
          </div>
        </div>
        <div class="field">
          <label>Coût setup / préparation (€)</label>
          <input type="number" id="f-setupCost" value="${v('setupCost', 0)}" min="0" step="1">
        </div>`;

      case 'laser': return descField + `
        <div class="field-row">
          <div class="field">
            <label>Temps machine (h)</label>
            <input type="number" id="f-machineH" value="${v('machineH', 0)}" min="0" step="0.1">
          </div>
          <div class="field">
            <label>Taux machine (€/h)</label>
            <input type="number" id="f-machineRate" value="${v('machineRate', s.rates.laser)}" min="0" step="1">
          </div>
        </div>
        <div class="field">
          <label>Coût matière (€)</label>
          <input type="number" id="f-materialCost" value="${v('materialCost', 0)}" min="0" step="0.5">
          <div class="field-hint">Coût brut de la tôle, feuille acrylique, etc.</div>
        </div>`;

      case 'machining': return descField + `
        <div class="field-row">
          <div class="field">
            <label>Heures machine + opérateur</label>
            <input type="number" id="f-hours" value="${v('hours', 0)}" min="0" step="0.25">
          </div>
          <div class="field">
            <label>Taux horaire (€/h)</label>
            <input type="number" id="f-rate" value="${v('rate', s.rates.machining)}" min="0" step="1">
          </div>
        </div>
        <div class="field">
          <label>Coût matière / outillage (€)</label>
          <input type="number" id="f-materialCost" value="${v('materialCost', 0)}" min="0" step="0.5">
        </div>`;

      case 'welding': return descField + `
        <div class="field-row">
          <div class="field">
            <label>Heures</label>
            <input type="number" id="f-hours" value="${v('hours', 0)}" min="0" step="0.25">
          </div>
          <div class="field">
            <label>Taux horaire (€/h)</label>
            <input type="number" id="f-rate" value="${v('rate', s.rates.welding)}" min="0" step="1">
          </div>
        </div>
        <div class="field">
          <label>Consommables (fil, gaz, électrodes...) (€)</label>
          <input type="number" id="f-consumables" value="${v('consumables', 0)}" min="0" step="0.5">
        </div>`;

      case 'scan3d': return descField + `
        <div class="field-row">
          <div class="field">
            <label>Heures (scan + post-traitement)</label>
            <input type="number" id="f-hours" value="${v('hours', 0)}" min="0" step="0.25">
          </div>
          <div class="field">
            <label>Taux horaire (€/h)</label>
            <input type="number" id="f-rate" value="${v('rate', s.rates.scan3d)}" min="0" step="1">
          </div>
        </div>`;

      case 'other': return descField + `
        <div class="field-row">
          <div class="field">
            <label>Quantité</label>
            <input type="number" id="f-qty" value="${v('qty', 1)}" min="0" step="1">
          </div>
          <div class="field">
            <label>Unité</label>
            <input type="text" id="f-unit" value="${esc(v('unit', 'forfait'))}" placeholder="ex: pièce, m², forfait">
          </div>
        </div>
        <div class="field">
          <label>Prix unitaire HT (€)</label>
          <input type="number" id="f-unitPrice" value="${v('unitPrice', 0)}" min="0" step="0.01">
        </div>`;

      default: return '';
    }
  },

  readItemFromModal() {
    const cat  = this.currentCategory;
    const g    = (id) => { const el = document.getElementById(id); return el ? (el.type === 'number' ? parseFloat(el.value) || 0 : el.value) : 0; };
    const base = { id: this.editingItemId || String(Date.now()), category: cat, desc: document.getElementById('f-desc')?.value || '' };

    switch (cat) {
      case 'cad':
        return { ...base, hours: g('f-hours'), rate: g('f-rate') };

      case 'print3d_plastic':
        return { ...base,
          printTimeH: g('f-printTimeH'), filamentG: g('f-filamentG'),
          filamentPriceKg: g('f-filamentPriceKg'), filamentType: g('f-filamentType'),
          printerW: g('f-printerW'), elecPrice: g('f-elecPrice'),
          setupCost: g('f-setupCost') };

      case 'print3d_metal':
        return { ...base,
          printTimeH: g('f-printTimeH'), powderG: g('f-powderG'),
          powderPriceKg: g('f-powderPriceKg'), metalAlloy: g('f-metalAlloy'),
          printerW: g('f-printerW'), elecPrice: g('f-elecPrice'),
          postH: g('f-postH'), postRate: g('f-postRate'),
          setupCost: g('f-setupCost') };

      case 'laser':
        return { ...base, machineH: g('f-machineH'), machineRate: g('f-machineRate'), materialCost: g('f-materialCost') };

      case 'machining':
        return { ...base, hours: g('f-hours'), rate: g('f-rate'), materialCost: g('f-materialCost') };

      case 'welding':
        return { ...base, hours: g('f-hours'), rate: g('f-rate'), consumables: g('f-consumables') };

      case 'scan3d':
        return { ...base, hours: g('f-hours'), rate: g('f-rate') };

      case 'other':
        return { ...base, qty: g('f-qty'), unit: g('f-unit') || 'forfait', unitPrice: g('f-unitPrice') };

      default: return base;
    }
  },

  refreshCostPreview() {
    try {
      const item  = this.readItemFromModal();
      const total = this.itemTotal(item);
      document.getElementById('item-cost-preview').textContent = `Coût : ${fmt(total)}`;
    } catch (_) {}
  },

  saveItem() {
    const item = this.readItemFromModal();
    if (this.editingItemId) {
      const idx = this.project.items.findIndex(i => i.id === this.editingItemId);
      if (idx !== -1) this.project.items[idx] = item;
    } else {
      this.project.items.push(item);
    }
    this.closeModal();
    this.renderItems();
  },

  closeModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
    this.editingItemId = null;
    this.currentCategory = null;
  },

  closeModalOverlay(e) {
    if (e.target === document.getElementById('modal-overlay')) this.closeModal();
  },

  // ── Summary ────────────────────────────────────────────────────────────────

  projectTotals() {
    const tva      = num('tvaRate', 20);
    const discount = num('discount', 0);
    const byCategory = {};
    let subtotal = 0;

    this.project.items.forEach(item => {
      const t = this.itemTotal(item);
      byCategory[item.category] = (byCategory[item.category] || 0) + t;
      subtotal += t;
    });

    const discountAmt = subtotal * (discount / 100);
    const ht          = subtotal - discountAmt;
    const tvaAmt      = ht * (tva / 100);
    const ttc         = ht + tvaAmt;

    return { subtotal, discount, discountAmt, ht, tva, tvaAmt, ttc, byCategory };
  },

  updateSummary() {
    const catDiv    = document.getElementById('summary-by-cat');
    const totalsDiv = document.getElementById('summary-totals');
    if (!catDiv || !totalsDiv) return;

    const t = this.projectTotals();

    catDiv.innerHTML = Object.keys(t.byCategory).length
      ? Object.entries(t.byCategory).map(([cat, total]) => `
          <div class="summary-cat-row">
            <span style="display:flex;align-items:center;gap:8px">
              <span class="cat-dot" style="background:${this.catColor(cat)}"></span>
              ${this.catLabel(cat)}
            </span>
            <span>${fmt(total)}</span>
          </div>`).join('')
      : '<p style="color:var(--text-muted);font-size:13px;padding:8px 0">Aucune prestation ajoutée.</p>';

    totalsDiv.innerHTML = `
      <div class="summary-total-row">
        <span>Sous-total</span><span>${fmt(t.subtotal)}</span>
      </div>
      ${t.discount > 0 ? `
      <div class="summary-total-row" style="color:#dc2626">
        <span>Remise (${t.discount}%)</span><span>− ${fmt(t.discountAmt)}</span>
      </div>` : ''}
      <div class="summary-total-row border-top">
        <span>Total HT</span><span>${fmt(t.ht)}</span>
      </div>
      <div class="summary-total-row tva">
        <span>TVA (${t.tva}%)</span><span>${fmt(t.tvaAmt)}</span>
      </div>
      <div class="summary-total-row ttc">
        <span>Total TTC</span><span>${fmt(t.ttc)}</span>
      </div>`;
  },

  // ── PDF / Print ────────────────────────────────────────────────────────────

  printDocument() {
    this.readProjectForm();
    const p = this.project;
    const s = this.settings;
    const t = this.projectTotals();

    const docLabel = p.document.type === 'devis' ? 'DEVIS' : 'FACTURE';
    const dateLine = p.document.type === 'devis'
      ? `Valable jusqu'au : ${fmtDate(p.document.validUntil)}`
      : `Échéance : ${fmtDate(p.document.dueDate)}`;

    const clientHeader = [p.client.company, p.client.name].filter(Boolean).join('<br>');

    const rows = p.items.map(item => {
      const total = this.itemTotal(item);
      const color = this.catColor(item.category);
      const { qty, unit, uprice } = this.printLineData(item);
      return `
        <tr>
          <td>
            <span class="print-cat-badge" style="background:${color}">${this.catLabel(item.category)}</span>
            ${esc(item.desc || '(sans description)')}
            <br><small>${this.itemDetails(item)}</small>
          </td>
          <td style="text-align:right">${qty}</td>
          <td style="text-align:right">${unit}</td>
          <td style="text-align:right">${uprice}</td>
          <td style="text-align:right;font-weight:700">${fmt(total)}</td>
        </tr>`;
    }).join('') || '<tr><td colspan="5" style="text-align:center;color:#9ca3af;padding:20px">Aucune prestation</td></tr>';

    document.getElementById('print-document').innerHTML = `
      <div class="print-page">
        <div class="print-header">
          <div>
            <div class="print-company-name">${esc(s.company.name || 'Mon Atelier')}</div>
            <div class="print-company-details">
              ${s.company.address ? s.company.address.replace(/\n/g, '<br>') : ''}
              ${s.company.phone   ? `<br>Tél : ${s.company.phone}` : ''}
              ${s.company.email   ? `<br>Email : ${s.company.email}` : ''}
              ${s.company.siret   ? `<br>SIRET : ${s.company.siret}` : ''}
              ${s.company.tvaNumber ? `<br>TVA : ${s.company.tvaNumber}` : ''}
            </div>
          </div>
          <div class="print-doc-block">
            <div class="print-doc-label">${docLabel}</div>
            <div class="print-doc-details">
              N° ${esc(p.document.number)}<br>
              Date : ${fmtDate(p.document.date)}<br>
              ${dateLine}
              ${p.document.projectName ? `<br>Réf. : ${esc(p.document.projectName)}` : ''}
            </div>
          </div>
        </div>

        <div class="print-client-wrapper">
          <div class="print-client">
            <div class="print-client-label">Facturer à</div>
            <div class="print-client-info">
              ${clientHeader ? `<strong>${clientHeader}</strong><br>` : ''}
              ${p.client.address ? p.client.address.replace(/\n/g, '<br>') : ''}
              ${p.client.email   ? `<br>${esc(p.client.email)}` : ''}
              ${p.client.phone   ? `<br>${esc(p.client.phone)}` : ''}
            </div>
          </div>
        </div>

        <table class="print-table">
          <thead>
            <tr>
              <th style="width:44%;text-align:left">Description</th>
              <th style="width:8%;text-align:right">Qté</th>
              <th style="width:10%;text-align:right">Unité</th>
              <th style="width:16%;text-align:right">P.U. HT</th>
              <th style="width:22%;text-align:right">Total HT</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>

        <div class="print-totals">
          ${t.discount > 0 ? `
          <div class="print-total-row">
            <span>Sous-total HT</span><span>${fmt(t.subtotal)}</span>
          </div>
          <div class="print-total-row discount">
            <span>Remise (${t.discount}%)</span><span>− ${fmt(t.discountAmt)}</span>
          </div>` : ''}
          <div class="print-total-row ht">
            <span>Total HT</span><span>${fmt(t.ht)}</span>
          </div>
          <div class="print-total-row tva">
            <span>TVA ${t.tva}%</span><span>${fmt(t.tvaAmt)}</span>
          </div>
          <div class="print-total-row ttc">
            <span>Total TTC</span><span>${fmt(t.ttc)}</span>
          </div>
        </div>

        ${p.options.notes ? `
        <div class="print-notes">
          <div class="print-notes-title">Conditions &amp; notes</div>
          <div>${esc(p.options.notes).replace(/\n/g, '<br>')}</div>
        </div>` : ''}

        ${s.company.paymentTerms ? `
        <div class="print-notes">
          <div class="print-notes-title">Modalités de paiement</div>
          <div>${esc(s.company.paymentTerms)}</div>
        </div>` : ''}

        <div class="print-footer">
          ${[s.company.name, s.company.siret ? 'SIRET ' + s.company.siret : '', s.company.tvaNumber ? 'TVA ' + s.company.tvaNumber : ''].filter(Boolean).join(' · ')}
        </div>
      </div>`;

    window.print();
  },

  printLineData(item) {
    const total = this.itemTotal(item);
    switch (item.category) {
      case 'cad':
        return { qty: String(item.hours), unit: 'h', uprice: fmt(item.rate) + '/h' };
      case 'print3d_plastic':
      case 'print3d_metal':
        return { qty: '1', unit: 'forfait', uprice: fmt(total) };
      case 'laser':
        return { qty: String(item.machineH), unit: 'h', uprice: fmt(item.machineRate) + '/h' };
      case 'machining':
      case 'welding':
      case 'scan3d':
        return { qty: String(item.hours), unit: 'h', uprice: fmt(item.rate) + '/h' };
      case 'other':
        return { qty: String(item.qty), unit: item.unit || 'u', uprice: fmt(item.unitPrice) };
      default:
        return { qty: '1', unit: '', uprice: fmt(total) };
    }
  },

  // ── Toast ──────────────────────────────────────────────────────────────────

  showToast(msg) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2800);
  },
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(n) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(n || 0);
}

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });
}

function isoDate(d) {
  return d.toISOString().split('T')[0];
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function num(id, def) {
  const el = document.getElementById(id);
  return el ? parseFloat(el.value) || def : def;
}

function set(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val ?? '';
}

document.addEventListener('DOMContentLoaded', () => App.init());
