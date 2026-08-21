"""Export a self-contained HTML snapshot of the Mark Six statistical dashboard.

The exported file intentionally contains only pre-locked records and client-side
interactions.  It does not execute Streamlit, train Python models, fetch results,
or modify blind-test records.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRIER_PATH = PROJECT_ROOT / "data" / "brier_tracking_history.json"
WEIGHT_PATH = PROJECT_ROOT / "data" / "weight_adjustment_history.json"
OUTPUT_PATH = PROJECT_ROOT / "exports" / "marksix_statistics_dashboard.html"
LABELS = {
    "fusion_top6": "融合模型 Top-6（基準）",
    "frequency50_50": "50% frequency_50 變體",
    "hot6": "熱門 6 配置",
    "multiscale_calibrated": "多尺度校準（研究配置）",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def build_payload() -> dict[str, Any]:
    """Create a limited, browser-safe snapshot from append-only JSON records."""
    brier_payload = _load_json(BRIER_PATH)
    weight_payload = _load_json(WEIGHT_PATH)
    records = brier_payload.get("records", [])
    return {
        "schema_version": 1,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "labels": LABELS,
        "brier_records": records if isinstance(records, list) else [],
        "weight_records": weight_payload.get("records", []) if isinstance(weight_payload.get("records", []), list) else [],
        "limitations": [
            "此 HTML 是已鎖定資料的離線快照；不會自動抓取開獎結果。",
            "純 HTML 不包含 Python／Streamlit 執行環境，不能重新訓練模型、執行 Bootstrap 或 Diebold–Mariano 檢定。",
            "正式盲測紀錄、每日更新、結果結算及權重啟用，仍只能在受保護的 Streamlit 服務中執行。",
        ],
    }


def build_html(payload: dict[str, Any]) -> str:
    """Return a single-file dashboard using only inline CSS and vanilla JavaScript."""
    safe_payload = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    template = r'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>六合彩統計研究儀表板｜離線快照</title>
<style>
:root{--ink:#172033;--muted:#667085;--paper:#f5f7fb;--card:#fff;--line:#dce3ef;--blue:#225ce5;--teal:#0f766e;--amber:#a55b00;--red:#b42318;--shadow:0 10px 30px rgba(23,32,51,.08)}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",sans-serif}.shell{max-width:1280px;margin:0 auto;padding:28px 22px 48px}.hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;border-bottom:1px solid var(--line);padding-bottom:22px}.eyebrow{color:var(--teal);font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}h1{font-size:clamp(26px,4vw,42px);letter-spacing:-.04em;margin:6px 0 9px}.subtitle{color:var(--muted);max-width:760px;line-height:1.65}.snapshot{font-size:12px;color:var(--muted);white-space:nowrap}.notice{background:#fff7e6;border:1px solid #ffd99c;color:#7a4400;border-radius:12px;padding:13px 15px;margin:18px 0;line-height:1.55}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 18px}.tab{background:transparent;border:1px solid var(--line);color:var(--muted);border-radius:999px;padding:9px 14px;cursor:pointer;font-weight:700}.tab.active{background:var(--ink);border-color:var(--ink);color:#fff}.panel{display:none}.panel.active{display:block}.grid{display:grid;gap:14px}.metrics{grid-template-columns:repeat(4,minmax(0,1fr))}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:var(--shadow)}.metric-label{font-size:12px;color:var(--muted);font-weight:700}.metric-value{font-size:27px;font-weight:800;letter-spacing:-.03em;margin-top:6px}.metric-note{color:var(--muted);font-size:12px;margin-top:5px}.section-title{margin:28px 0 12px;font-size:20px}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0}.toolbar label{font-size:13px;font-weight:700;color:var(--muted)}select,input[type=range]{accent-color:var(--blue)}select{padding:9px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink)}table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;font-size:13px;vertical-align:top}th{background:#f8fafc;color:var(--muted);font-size:12px}tr:last-child td{border-bottom:0}.bars{display:grid;gap:10px}.bar-row{display:grid;grid-template-columns:minmax(126px,220px) 1fr 76px;gap:10px;align-items:center;font-size:13px}.track{height:11px;border-radius:999px;background:#e9eef7;overflow:hidden}.fill{height:100%;background:linear-gradient(90deg,var(--blue),#6b94ff);border-radius:999px}.pill{display:inline-flex;align-items:center;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:800}.pill.wait{background:#fff7e6;color:#7a4400}.pill.locked{background:#edf7f4;color:var(--teal)}.empty{border:1px dashed #bac6d8;border-radius:14px;padding:24px;color:var(--muted);background:#fbfcfe;line-height:1.65}.limit-list{margin:0;padding-left:20px;line-height:1.7;color:var(--muted)}button.download{margin-top:16px;background:var(--blue);color:#fff;border:0;border-radius:9px;padding:10px 13px;font-weight:800;cursor:pointer}.foot{color:var(--muted);font-size:12px;margin-top:30px;line-height:1.6}@media(max-width:760px){.hero{align-items:flex-start;flex-direction:column}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.bar-row{grid-template-columns:104px 1fr 62px}.shell{padding:18px 14px 36px}.snapshot{white-space:normal}}
</style>
</head>
<body><main class="shell">
<header class="hero"><div><div class="eyebrow">Mark Six · Statistical Research</div><h1>四配置 Brier 與權重凍結監控</h1><p class="subtitle">可離線開啟的單檔互動快照。資料只包含開獎前已鎖定的機率紀錄與權重版本，不含即時模型運算。</p></div><div class="snapshot" id="snapshot"></div></header>
<div class="notice">本檔案只供統計教育與研究追蹤。六合彩屬獨立隨機事件；候選、Brier 或權重不構成投注建議或中獎保證。</div>
<nav class="tabs"><button class="tab active" data-panel="brier">Brier 追蹤</button><button class="tab" data-panel="weights">權重與凍結</button><button class="tab" data-panel="about">快照範圍</button></nav>
<section class="panel active" id="brier"><div class="grid metrics" id="brierMetrics"></div><h2 class="section-title">已鎖定的四配置紀錄</h2><div class="toolbar"><label>目標期數 <select id="drawSelect"></select></label><label>配置 <select id="configSelect"></select></label><label>顯示前 <input id="topN" type="range" min="6" max="20" value="10"> <span id="topNValue">10</span> 個機率號碼</label></div><div id="recordStatus"></div><div class="card"><h3 style="margin-top:0">完整 49 號機率向量中的最高排序</h3><div class="bars" id="probabilityBars"></div></div><h2 class="section-title">四配置候選 Top-6</h2><div id="variantTable"></div></section>
<section class="panel" id="weights"><div class="grid metrics" id="weightMetrics"></div><h2 class="section-title">目前權重</h2><div class="card"><div class="bars" id="weightBars"></div></div><h2 class="section-title">資格閘門與 50 期確認</h2><div id="gateTable"></div><h2 class="section-title">已鎖定權重版本歷史</h2><div id="weightHistory"></div></section>
<section class="panel" id="about"><h2 class="section-title">這份獨立 HTML 可做甚麼</h2><div class="card"><ul class="limit-list"><li>在瀏覽器內切換已嵌入的目標期數與四個配置。</li><li>以滑桿瀏覽每個配置完整 49 號機率向量的前 6–20 名。</li><li>查看已鎖定候選、權重版本、資格閘門及 50 期凍結進度。</li><li>下載嵌入本檔案的 JSON 快照，以供本機稽核。</li></ul><h2 class="section-title">必須留在受保護 Streamlit 服務的功能</h2><ul class="limit-list" id="limitations"></ul><button class="download" id="downloadJson">下載嵌入資料 JSON</button></div></section>
<p class="foot">離線快照不會連線、不會更新結果、不會修改盲測記錄。請以受保護的 Streamlit 儀表板作正式盲測、每日更新及統計檢定來源。</p>
</main><script>const SNAPSHOT=__PAYLOAD__;
const labels=SNAPSHOT.labels;const records=SNAPSHOT.brier_records||[];const weightRecords=SNAPSHOT.weight_records||[];const $=s=>document.querySelector(s);const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
$('#snapshot').textContent='離線快照：'+new Date(SNAPSHOT.exported_at_utc).toLocaleString('zh-HK',{timeZone:'Asia/Hong_Kong'});
document.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('.tab,.panel').forEach(e=>e.classList.remove('active'));btn.classList.add('active');$('#'+btn.dataset.panel).classList.add('active')}));
function metric(label,value,note){return `<div class="card"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value)}</div><div class="metric-note">${esc(note)}</div></div>`}
function record(){return records.find(r=>String(r.target_draw)===$('#drawSelect').value)||records[0]}
function selectedConfig(){return $('#configSelect').value}
function renderBrier(){const r=record();const key=selectedConfig();const vector=(r?.configuration_probabilities||{})[key]||[];const settled=Array.isArray(r?.actual_main_numbers)&&r.actual_main_numbers.length===6;$('#brierMetrics').innerHTML=[metric('完整機率鎖定期數',records.length,'只計 49 號完整向量'),metric('共同已結算 Brier 期數',settled?1:0,settled?'此快照包含已結算結果':'尚待官方正選結果'),metric('正式推論門檻','100 期','不足時只屬描述性'),metric('目前狀態',settled?'已結算':'待結果',r?.target_draw||'—')].join('');$('#recordStatus').innerHTML=`<div class="card"><span class="pill ${settled?'locked':'wait'}">${settled?'已結算':'已鎖定，等待官方結果'}</span><p class="subtitle">目標期 ${esc(r?.target_draw)}｜目標日期 ${esc(r?.target_date)}｜鎖定時間 ${esc(r?.locked_at_utc)}。離線快照不會自行取得或寫入結果。</p></div>`;const n=Number($('#topN').value);$('#topNValue').textContent=n;const ranked=vector.map((p,i)=>({n:i+1,p:Number(p)})).sort((a,b)=>b.p-a.p).slice(0,n);const maximum=ranked[0]?.p||1;$('#probabilityBars').innerHTML=ranked.map(item=>`<div class="bar-row"><strong>${String(item.n).padStart(2,'0')} 號</strong><div class="track"><div class="fill" style="width:${(item.p/maximum*100).toFixed(2)}%"></div></div><span>${(item.p*100).toFixed(3)}%</span></div>`).join('')||'<div class="empty">此配置未包含完整機率資料。</div>';const variants=r?.variants||[];$('#variantTable').innerHTML=variants.length?`<table><thead><tr><th>配置</th><th>已鎖定 Top-6</th></tr></thead><tbody>${variants.map(v=>`<tr><td>${esc(v.label||labels[v.key]||v.key)}</td><td>${(v.numbers||[]).map(x=>String(x).padStart(2,'0')).join(' · ')}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">尚無已鎖定的候選組合。</div>'}
function renderWeights(){const active=weightRecords.at(-1);const weights=active?.proposed_weights||Object.fromEntries(Object.keys(labels).map(k=>[k,.25]));const frozen=active?.status==='frozen';const completed=Number(active?.freeze_completed_draws||0);$('#weightMetrics').innerHTML=[metric('目前版本',active?.version||'baseline-equal-v1',active?'已鎖定版本':'觀察期基準'),metric('目前階段',frozen?'50 期凍結盲測':'共同盲測累積','不自動修改權重'),metric('凍結確認',`${completed}/50`,frozen?'只作樣本外確認':'尚未啟動'),metric('權重邊界','10% – 55%','總和固定為 100%')].join('');$('#weightBars').innerHTML=Object.entries(labels).map(([k,label])=>`<div class="bar-row"><strong>${esc(label)}</strong><div class="track"><div class="fill" style="width:${(weights[k]*100).toFixed(2)}%"></div></div><span>${(weights[k]*100).toFixed(1)}%</span></div>`).join('');$('#gateTable').innerHTML=`<table><thead><tr><th>閘門</th><th>規則</th><th>現況</th></tr></thead><tbody><tr><td>共同已結算機率</td><td>至少 100 期</td><td>本快照尚未達門檻</td></tr><tr><td>雙方法推論</td><td>Bootstrap 與 DM 經 Holm 校正均通過</td><td>等待共同樣本</td></tr><tr><td>實際效果量</td><td>Brier Skill Score ≥ +0.5%</td><td>等待正式檢定</td></tr><tr><td>樣本外確認</td><td>候選權重凍結 50 期</td><td>${frozen?`${completed}/50`:'尚未開始'}</td></tr></tbody></table>`;$('#weightHistory').innerHTML=weightRecords.length?`<table><thead><tr><th>版本</th><th>狀態</th>${Object.values(labels).map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${weightRecords.map(r=>`<tr><td>${esc(r.version)}</td><td>${esc(r.status)}</td>${Object.keys(labels).map(k=>`<td>${((r.proposed_weights||{})[k]*100||0).toFixed(1)}%</td>`).join('')}</tr>`).join('')}</tbody></table>`:'<div class="empty">尚未有通過資格閘門的候選權重版本。系統維持等權重觀察期，避免在資料不足時追逐短期波動。</div>'}
function init(){const draw=$('#drawSelect'),config=$('#configSelect');records.forEach(r=>draw.insertAdjacentHTML('beforeend',`<option value="${esc(r.target_draw)}">${esc(r.target_draw)} · ${esc(r.target_date)}</option>`));Object.entries(labels).forEach(([k,v])=>config.insertAdjacentHTML('beforeend',`<option value="${esc(k)}">${esc(v)}</option>`));[draw,config,$('#topN')].forEach(el=>el.addEventListener('input',renderBrier));$('#limitations').innerHTML=SNAPSHOT.limitations.map(x=>`<li>${esc(x)}</li>`).join('');$('#downloadJson').addEventListener('click',()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(SNAPSHOT,null,2)],{type:'application/json'}));a.download='marksix_dashboard_snapshot.json';a.click();URL.revokeObjectURL(a.href)});renderBrier();renderWeights()}init();
</script></body></html>'''
    return template.replace("__PAYLOAD__", safe_payload)


def export_dashboard(output_path: Path = OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html(build_payload()), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    print(export_dashboard())
