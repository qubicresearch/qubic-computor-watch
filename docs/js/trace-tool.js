'use strict';
// Shared money-trail lookup tool. Used on the main dashboard and every per-epoch
// report page (docs/epoch/*.html) -- one copy, so a fix here fixes everywhere.
// Expects these element ids to exist on the including page: lookupInput, lookupBtn,
// lookupResult, historySection, historyControls, historyTable, historyBtn,
// historyPrevBtn, historyNextBtn, trailView, trailBackBtn, trailClearBtn, hubTable,
// bookmarkletLink.

const ZERO_ID = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFXIB';

// Every hop we've directly verified for each network. If a looked-up identity's activity
// touches ANY of these, it's part of the same joint operation, not a separate entity —
// that needs to be obvious to whoever uses the lookup tool, not just the well-known names.
const HUBS = [
  // --- MinerLab/JetSki family: seeding/collection hubs ---
  ['TKOG (seeding hub)', 'TKOGFEQBANSKPBSLDXZXDKVCAKUANUSCAFCWOPQWKEZTCXRTVGYLKBHGLVIJ', 'MinerLab/JetSki'],
  ['YNRE (seeding hub)', 'YNREMHVGUYWANGCMAUIKYAKFLPBANLNGSSYXSMHVJBPMBGMFTCWKEBWENPQN', 'MinerLab/JetSki'],
  ['ZTQM (collection hub)', 'ZTQMSNBHXHOKQFXAULPQJPAMLMXANZCEUEWAYTCHUGNOEZNZFVFQORUDIIWC', 'MinerLab/JetSki'],
  ['TMNN (collection hub)', 'TMNNSVZZPYTZSGOOOHMXIJINBYNCSYTTVVQPSIRNAEESGORHENUKWLAGOFFC', 'MinerLab/JetSki'],
  ['MLABN', 'MLABNEHWNYBDOFNHELXZAFVDDWCCIGFKYZMFSFKCECAWATTFPCEHRKBFOKPD', 'MinerLab/JetSki'],
  ['MLABD', 'MLABDNEGKEJLIFFHLCHLDFUVYSHALWSNQXLECAYBADULQESQIYHIULJELLXG', 'MinerLab/JetSki'],
  ['MLABR', 'MLABRECTCPJJFGHOMEDVQKOMLPQDRXIJRRWQAMOXXBEKHUWUCTFZSEYDYTIM', 'MinerLab/JetSki'],
  ['MLABZ', 'MLABZCULRLUKHCSJBCDUUKUTUDFCAJVNRGMKTGTHCFUOUYCPUGFCOKBFLFTC', 'MinerLab/JetSki'],
  // --- MinerLab/JetSki family: clearinghouse and downstream ---
  ['LKBOPOUKGSYT (clearinghouse)', 'LKBOPOUKGSYTODWVEPXHUXDTRSOCDOXXXIEAGBJXAGJRMGXRXMCHDNCHWRLK', 'MinerLab/JetSki'],
  ['GXITF (aggregator)', 'GXITFZPMTHWNUAWQQVCHXZRKOVMDMWOBRVCDCUDHYBJMEJOYDYDELZAFEIIA', 'MinerLab/JetSki'],
  ['BBMMA (relay)', 'BBMMAXUALHUWHEVSALTYQVYVTRHBVPVMZCJEFIVAJDXVYFITYPIOGGQGCWTC', 'MinerLab/JetSki'],
  ['VUEY (MEXC exchange)', 'VUEYKUCYYHXKDGOSCWAIEECECDBCXVUSUAJRVXUQVAQPGIOABLGGLXDAXTNK', 'MinerLab/JetSki'],
  ['UHLSQ (founding wallet)', 'UHLSQVOWHBOHREGYHCQDWXAQHHFCZCZNCDAYIVRJVCGOUNOEHOAFUPMDICKF', 'MinerLab/JetSki'],
  ['GDXY (root wallet, 2024)', 'GDXYIXYSWTZHOEMBWFUTQCNIOYTBOTWJQNMQHXOGBFWUYVCPZDNKWSFHSGKL', 'MinerLab/JetSki'],
  ['JETSKIYUBUPF', 'JETSKIYUBUPFUCODLCBAJNFVCINABCOQIEXEZWNWMAFGBKPBOFTUCECCCSXG', 'MinerLab/JetSki'],
  ['JETSKIQRDEIV', 'JETSKIQRDEIVUDRAXYUVZOBHJAMCWFSOJBDKBPRDKCWSCHQHDBJHCPIEJUAH', 'MinerLab/JetSki'],
  ['JETSKIMZKTSL', 'JETSKIMZKTSLXCGBKJQNNSOBLFQDTCYBJPFLYGHVRFSITZNCDHCKSSRAESFM', 'MinerLab/JetSki'],
  // --- MinerLab/JetSki family: 1M-denominated branch ---
  ['NNGXGF', 'NNGXGFLCDZODBCBFJKIUTEYXYLODTBCQDMOHAASBJDNEUHKBOTDXSCWEZUGA', 'MinerLab/JetSki'],
  ['NZOIEU', 'NZOIEUECLNONOFRMFPPPXGIJWSVBGROIDCAAYIBRIATTMQLTQRPEGNXFBGFN', 'MinerLab/JetSki'],
  ['JJAKPG', 'JJAKPGZYNPMCCGXHIKBBRSGSHTYAXWKMEQQJGPSAIHZXHPPSZUXAXLAGSIQD', 'MinerLab/JetSki'],
  ['TZRLYH', 'TZRLYHJOEALYVGALTUICKBEQYWABCNVQSQCQBBTEREUUXKPWGXWROZYBIJHN', 'MinerLab/JetSki'],
  ['KCOB (relay)', 'KCOBMVHDFGJXGBDOEVTBTQPRSOEBRWUOXKTTQYZECEUXNNIEDJNKATRFZQVM', 'MinerLab/JetSki'],
  ['CLJHHZVRWA (major hub)', 'CLJHHZVRWAVBEAECXMCEIZOZOJLAMWCQMNYXXHQXOBGRUCXKVZCMBQECQJPE', 'MinerLab/JetSki'],
  // --- qli family: collection hubs ---
  ['IHDR', 'IHDRUFFVQWVCAHXXJSXVCYKDHLKAOJDPETLKJUHVFEHRXOSGMDYAJTPFDJVJ', 'qli'],
  ['VAQA', 'VAQAOZKHUDRSXEKASNTYIPMABNVAWHORIXGNCURPDFUKJOMFAMBMLJSCVSSJ', 'qli'],
  ['KOYO', 'KOYOTPJVZIONSFEZLVAYHVZANCHDILVZJOADLOIMAATEMBIIPCLMAUKFLYFB', 'qli'],
  ['JBWF', 'JBWFGUWXGRIQJAIRKIEXMTEEQETAWDSMWENEHVFXTFFJDKZMMQVCYMGHBVMJ', 'qli'],
  ['PCUTRGWY', 'PCUTRGWYFCMGGGVLFRPLNNEJQRABPKPOQYYYDUFAPAKPIJYQVJJMDUKAKZFL', 'qli'],
  ['KDHVRGXD', 'KDHVRGXDVVLVZBUFZRAWKGDUMJSBESEYRBDBGKHYBGOIPVIWGKEZWJSBREAK', 'qli'],
  ['LHDR (epoch-227 era)', 'LHDRZRNITLNVCEVCHDVASGFWPWUCQBQURBIXLDWIMAZQILTNAFGVDEXDKIYG', 'qli'],
  ['DMRK (epoch-227 era)', 'DMRKLYUUQWXNGBQUQBHWSMUJORGCOJQYQINFEUDMPANYZAJILKBQRXYAKNTC', 'qli'],
  // --- qli family: epoch-230 transit hubs (confirmed 2026-09-19) ---
  ['TCRX (transit)', 'TCRXZUYBIKMMJAWWIMRNQCNICPFANSXNAGMRNDMTKCVYYUVYIBTYXQVANGQO', 'qli'],
  ['FSDR (transit)', 'FSDROWWKMPUVKARPREZZWIJVDMKAWMSMHAYPUCMZDDFKWSTXFGZOKLYGHMFJ', 'qli'],
  ['TOUP (transit)', 'TOUPGQICIUUFYCXIESJUINIUPDOCOEVIMSVXFACVVGULZHUHFNLOZVWFMUEA', 'qli'],
  ['VOYI (transit)', 'VOYIONBAFMJONFJTDOSOSWXHXRNBYMAKHZMUCILVRBACOCLQQCNUIDAHIVUK', 'qli'],
];

// Real, confirmed next-hop for each hub (from direct on-chain tracing, not inferred).
// Lets the lookup tool show the FULL path forward to the final destination, not just
// "touches a known hub" — if it's part of the same joint network, that has to be obvious.
const NEXT_HOP = {
  // TKOG (seeding hub) removed 2026-09-06: re-checked TKOG's full 3,428-transaction
  // history (both directions, full coverage) and it never once transacted with
  // LKBOPOUKGSYT. That claimed link wasn't reproducible — removed rather than left
  // wrong. TKOG's own downstream is currently unverified; re-check before re-adding.
  'YNRE (seeding hub)': ['LKBOPOUKGSYT (clearinghouse)'],
  'ZTQM (collection hub)': ['LKBOPOUKGSYT (clearinghouse)'],
  'TMNN (collection hub)': ['LKBOPOUKGSYT (clearinghouse)'],
  'MLABN': ['LKBOPOUKGSYT (clearinghouse)'],
  'MLABD': ['LKBOPOUKGSYT (clearinghouse)'],
  'MLABR': ['LKBOPOUKGSYT (clearinghouse)'],
  'GDXY (root wallet, 2024)': ['LKBOPOUKGSYT (clearinghouse)'],
  'UHLSQ (founding wallet)': ['GXITF (aggregator)'],
  'LKBOPOUKGSYT (clearinghouse)': ['JETSKIYUBUPF', 'JETSKIQRDEIV', 'JETSKIMZKTSL', 'GXITF (aggregator)'],
  'GXITF (aggregator)': ['BBMMA (relay)'],
  'NNGXGF': ['KCOB (relay)'],
  'NZOIEU': ['KCOB (relay)'],
  'JJAKPG': ['KCOB (relay)'],
  'TZRLYH': ['KCOB (relay)'],
  'KCOB (relay)': ['CLJHHZVRWA (major hub)'],
  'CLJHHZVRWA (major hub)': ['BBMMA (relay)'],
  'BBMMA (relay)': ['VUEY (MEXC exchange)'],
  'IHDR': ['QLI-branded wallets'],
  'VAQA': ['QLI-branded wallets'],
  'KOYO': ['QLI-branded wallets'],
  'JBWF': ['QLI-branded wallets'],
  'PCUTRGWY': ['QLI-branded wallets'],
  'KDHVRGXD': ['QLI-branded wallets'],
  'LHDR (epoch-227 era)': ['QLI-branded wallets'],
  'DMRK (epoch-227 era)': ['QLI-branded wallets'],
  'TCRX (transit)': ['QLI-branded wallets'],
  'FSDR (transit)': ['QLI-branded wallets'],
  'TOUP (transit)': ['QLI-branded wallets'],
  'VOYI (transit)': ['QLI-branded wallets'],
};

// Returns a simple, flat list of "steps" — each step is an array of one or more
// hub names reachable at that depth (more than one when a hub forwards to several
// places at once, e.g. the clearinghouse splitting to 3 JetSki wallets).
function tracePath(startName) {
  const steps = [[startName]];
  let current = [startName];
  const seen = new Set(current);
  for (let guard = 0; guard < 10; guard++) {
    const nextSet = new Set();
    for (const name of current) {
      for (const n of (NEXT_HOP[name] || [])) {
        if (!seen.has(n)) nextSet.add(n);
      }
    }
    if (!nextSet.size) break;
    current = [...nextSet];
    current.forEach(n => seen.add(n));
    steps.push(current);
  }
  return steps;
}

function renderPath(steps) {
  return steps.map(step => step.join(' / ')).join(' &rarr; ');
}

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

async function loadHubBalances() {
  const table = document.getElementById('hubTable');
  if (!table) return;
  for (const [name, addr, family] of HUBS) {
    const row = document.createElement('tr');
    row.innerHTML = `<td>${name}</td><td class="mono">${addr}</td><td class="num" id="bal-${addr}">…</td><td>${family}</td>`;
    table.appendChild(row);
    getJson(`https://rpc.qubic.org/v1/balances/${addr}`).then(d => {
      document.getElementById(`bal-${addr}`).textContent = Number(d.balance.balance).toLocaleString() + ' QU';
    }).catch(() => {
      document.getElementById(`bal-${addr}`).textContent = 'error';
    });
  }
}

// ---------- trace trail (click-to-extend breadcrumb, saved per-browser) ----------
let trail = [];
try { trail = JSON.parse(localStorage.getItem('traceTrail') || '[]'); } catch (e) { trail = []; }

function saveTrail() { localStorage.setItem('traceTrail', JSON.stringify(trail)); }
function shortId(id) { return id.slice(0, 8) + '&hellip;' + id.slice(-4); }

function renderTrail() {
  const el = document.getElementById('trailView');
  if (!el) return;
  if (!trail.length) { el.innerHTML = '<span class="small">Nothing traced yet — look up an identity above to start.</span>'; return; }
  el.innerHTML = trail.map((id, i) => {
    const isLast = i === trail.length - 1;
    const label = `<span title="${id}" style="cursor:pointer; ${isLast ? 'color:var(--acc); font-weight:bold;' : 'color:var(--fg); text-decoration:underline;'}" data-trail-idx="${i}">${shortId(id)}</span>`;
    return i === 0 ? label : ' &rarr; ' + label;
  }).join('');
  el.querySelectorAll('[data-trail-idx]').forEach(node => {
    node.onclick = () => {
      const idx = parseInt(node.getAttribute('data-trail-idx'), 10);
      trail = trail.slice(0, idx + 1);
      saveTrail();
      renderTrail();
      document.getElementById('lookupInput').value = trail[idx];
      doLookup(trail[idx], false);
    };
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const backBtn = document.getElementById('trailBackBtn');
  const clearBtn = document.getElementById('trailClearBtn');
  if (backBtn) backBtn.onclick = () => {
    if (trail.length <= 1) { trail = []; saveTrail(); renderTrail(); document.getElementById('lookupResult').textContent = 'Trail cleared.'; return; }
    trail.pop();
    saveTrail();
    renderTrail();
    const prev = trail[trail.length - 1];
    document.getElementById('lookupInput').value = prev;
    doLookup(prev, false);
  };
  if (clearBtn) clearBtn.onclick = () => { trail = []; saveTrail(); renderTrail(); };
  renderTrail();

  // ---------- bookmarklet: reads the address off an explorer.qubic.org address-page URL ----------
  const bookmarkletLink = document.getElementById('bookmarkletLink');
  if (bookmarkletLink) {
    const base = location.origin + location.pathname;
    const code = `javascript:(function(){var m=location.pathname.match(/address\\/([A-Za-z]{60})/);var a=m?m[1].toUpperCase():null;if(!a){alert('No 60-letter Qubic address found in this page URL. Make sure you are on an explorer.qubic.org address page.');return;}window.open('${base}?add='+a,'qubicTrail');})();`;
    bookmarkletLink.setAttribute('href', code);
  }

  // If we were opened/navigated via the bookmarklet (?add=ADDRESS), pick it up, add it to
  // the trail, look it up immediately, and strip it from the URL so a refresh doesn't re-add it.
  const params = new URLSearchParams(location.search);
  const add = (params.get('add') || '').trim().toUpperCase();
  if (/^[A-Z]{60}$/.test(add)) {
    history.replaceState({}, '', location.pathname);
    document.getElementById('lookupInput').value = add;
    doLookup(add, true);
  }

  const lookupBtn = document.getElementById('lookupBtn');
  if (lookupBtn) lookupBtn.onclick = () => {
    const id = document.getElementById('lookupInput').value.trim().toUpperCase();
    doLookup(id, true);
  };

  const historyBtn = document.getElementById('historyBtn');
  if (historyBtn) historyBtn.onclick = () => {
    historyPage = 0;
    document.getElementById('historyControls').style.display = 'block';
    document.getElementById('historyBtn').textContent = 'Refresh transaction history';
    loadHistoryPage(historyPage);
  };
  const historyPrevBtn = document.getElementById('historyPrevBtn');
  if (historyPrevBtn) historyPrevBtn.onclick = () => { if (historyPage > 0) { historyPage--; loadHistoryPage(historyPage); } };
  const historyNextBtn = document.getElementById('historyNextBtn');
  if (historyNextBtn) historyNextBtn.onclick = () => { historyPage++; loadHistoryPage(historyPage); };

  loadHubBalances();
});

async function doLookup(id, appendToTrail = true) {
  const out = document.getElementById('lookupResult');
  if (!/^[A-Z]{60}$/.test(id)) { out.innerHTML = '<span class="status-bad">Identity must be 60 letters A-Z.</span>'; return; }
  out.textContent = 'Checking…';
  try {
    const balResp = await fetch(`https://rpc.qubic.org/v1/balances/${id}`);
    const bal = await balResp.json();
    // Check the FIRST 5 transactions (ascending), not the most recent — seeding is
    // almost always an identity's very first transaction ever, so this is both
    // lighter and more targeted than pulling a large recent-N window.
    const txResp = await fetch(`https://rpc.qubic.org/v2/identities/${id}/transfers?desc=false&pageSize=5&page=0`);
    const txData = await txResp.json();
    const totalCount = txData.pagination ? txData.pagination.totalRecords : 0;
    const firstTxs = (txData.transactions || []).map(t => t.transactions[0].transaction);
    const hubMatch = HUBS.find(([, addr]) => firstTxs.some(t => t.destId === addr || t.sourceId === addr));
    let pathHtml = `<span class="status-ok">no known hub in the first ${firstTxs.length} of ${totalCount} transactions</span>`;
    if (hubMatch) {
      const steps = tracePath(hubMatch[0]);
      pathHtml = `<span class="status-warn">part of the ${hubMatch[2]} network</span><br>` +
        `<div class="mono" style="margin-top:6px; font-size:0.8rem; color:var(--fg);">this identity &rarr; ${renderPath(steps)}</div>`;
    }
    // The counterpart on this identity's very first transaction — whether or not it's
    // a hub we've already named, following it one more hop is the manual-tracing move
    // this whole investigation has been doing by hand all session. Make it one click.
    const first = firstTxs[0];
    let funderHtml = '<span class="small">no transactions at all</span>';
    if (first) {
      const counterpart = first.destId === id ? first.sourceId : first.destId;
      const direction = first.destId === id ? 'received from' : 'sent to';
      funderHtml = `${direction} <span class="mono">${counterpart}</span> (${Number(first.amount).toLocaleString()} QU, tick ${first.tickNumber}) ` +
        `<button data-funder="${counterpart}" style="margin-left:8px; padding:2px 8px;">Trace this &rarr;</button>`;
    }
    out.innerHTML = `
      <div><strong>Balance:</strong> ${Number(bal.balance.balance).toLocaleString()} QU</div>
      <div><strong>Total transactions:</strong> ${totalCount}</div>
      <div style="margin-top:8px;"><strong>Real money-trail:</strong><br>${pathHtml}</div>
      <div style="margin-top:8px;"><strong>First-ever transaction:</strong><br>${funderHtml}</div>
    `;
    const btn = out.querySelector('[data-funder]');
    if (btn) btn.onclick = () => {
      const next = btn.getAttribute('data-funder');
      document.getElementById('lookupInput').value = next;
      doLookup(next, true);
    };
    if (appendToTrail && (trail.length === 0 || trail[trail.length - 1] !== id)) {
      trail.push(id);
      saveTrail();
      renderTrail();
    }
    currentLookupId = id;
    document.getElementById('historySection').style.display = 'block';
    document.getElementById('historyControls').style.display = 'none';
    document.getElementById('historyTable').innerHTML = '<tr><th>Date</th><th>Tick</th><th>Direction</th><th>Amount</th><th>Counterparty</th></tr>';
    document.getElementById('historyBtn').textContent = 'Show full transaction history';
  } catch (e) {
    out.innerHTML = '<span class="status-bad">Lookup failed: ' + e.message + '</span>';
  }
}

// ---------- full paginated transaction history, most recent first, every counterparty clickable ----------
let currentLookupId = null;
let historyPage = 0;
const HISTORY_PAGE_SIZE = 25;

async function loadHistoryPage(page) {
  const table = document.getElementById('historyTable');
  const lbl = document.getElementById('historyPageLbl');
  table.innerHTML = '<tr><th>Date</th><th>Tick</th><th>Direction</th><th>Amount</th><th>Counterparty</th></tr><tr><td colspan="5" class="small">Loading…</td></tr>';
  try {
    const d = await getJson(`https://rpc.qubic.org/v2/identities/${currentLookupId}/transfers?desc=true&pageSize=${HISTORY_PAGE_SIZE}&page=${page}`);
    const rows = (d.transactions || []).map(t => ({ ...t.transactions[0].transaction, timestamp: t.transactions[0].timestamp }));
    table.innerHTML = '<tr><th>Date</th><th>Tick</th><th>Direction</th><th>Amount</th><th>Counterparty</th></tr>';
    if (!rows.length) {
      table.innerHTML += '<tr><td colspan="5" class="small">No transactions on this page.</td></tr>';
    }
    for (const tx of rows) {
      const isOut = tx.sourceId === currentLookupId;
      const counterparty = isOut ? tx.destId : tx.sourceId;
      const date = new Date(Number(tx.timestamp || 0)).toISOString().slice(0, 10);
      const row = document.createElement('tr');
      row.innerHTML = `
        <td class="small">${date}</td>
        <td class="num">${tx.tickNumber}</td>
        <td>${isOut ? '<span class="status-bad">out</span>' : '<span class="status-ok">in</span>'}</td>
        <td class="num">${Number(tx.amount).toLocaleString()}</td>
        <td class="mono" style="cursor:pointer; text-decoration:underline;" data-trace="${counterparty}" title="Click to trace this address">${counterparty}</td>
      `;
      table.appendChild(row);
    }
    table.querySelectorAll('[data-trace]').forEach(cell => {
      cell.onclick = () => {
        const addr = cell.getAttribute('data-trace');
        document.getElementById('lookupInput').value = addr;
        doLookup(addr, true);
        window.scrollTo({ top: document.getElementById('lookupInput').getBoundingClientRect().top + window.scrollY - 20, behavior: 'smooth' });
      };
    });
    const total = d.pagination ? d.pagination.totalRecords : rows.length;
    const totalPages = Math.max(1, Math.ceil(total / HISTORY_PAGE_SIZE));
    lbl.textContent = `page ${page + 1} of ${totalPages} (${total} total transactions, newest first)`;
    document.getElementById('historyPrevBtn').disabled = page === 0;
    document.getElementById('historyNextBtn').disabled = page + 1 >= totalPages;
  } catch (e) {
    table.innerHTML = '<tr><th>Date</th><th>Tick</th><th>Direction</th><th>Amount</th><th>Counterparty</th></tr><tr><td colspan="5" class="status-bad">Failed to load: ' + e.message + '</td></tr>';
  }
}
