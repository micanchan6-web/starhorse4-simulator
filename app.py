"""
スターホース4風 競馬シミュレーター - Streamlit GUI版
"""

import io
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as _fm
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ============================================================
# 設定ファイルのパスと永続化ヘルパー
# ============================================================
CONFIGS_FILE = Path(__file__).parent / "saved_configs.json"
PLAYER_PRESET_KEY = "__player_horse_presets__"


def _load_all_configs() -> dict:
    """保存済みプリセットをすべて読み込む"""
    if CONFIGS_FILE.exists():
        return json.loads(CONFIGS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_config(name: str, horse_data: list) -> None:
    """現在の馬データをプリセットとしてJSONファイルに保存する"""
    configs = _load_all_configs()
    configs[name] = horse_data
    CONFIGS_FILE.write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")


def _delete_config(name: str) -> None:
    """指定名のプリセットを削除する"""
    configs = _load_all_configs()
    configs.pop(name, None)
    CONFIGS_FILE.write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_player_presets() -> dict:
    """プレイヤー5枠プリセットを読み込む"""
    configs = _load_all_configs()
    data = configs.get(PLAYER_PRESET_KEY, {})
    return data if isinstance(data, dict) else {}


def _save_player_preset(name: str, slots: list[tuple[str, float]]) -> None:
    """プレイヤー5枠プリセットを保存する"""
    configs = _load_all_configs()
    presets = configs.get(PLAYER_PRESET_KEY, {})
    if not isinstance(presets, dict):
        presets = {}
    presets[name] = slots
    configs[PLAYER_PRESET_KEY] = presets
    CONFIGS_FILE.write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")


def _delete_player_preset(name: str) -> None:
    """プレイヤー5枠プリセットを削除する"""
    configs = _load_all_configs()
    presets = configs.get(PLAYER_PRESET_KEY, {})
    if isinstance(presets, dict):
        presets.pop(name, None)
    configs[PLAYER_PRESET_KEY] = presets if isinstance(presets, dict) else {}
    CONFIGS_FILE.write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# matplotlib 日本語フォント設定（IPAexGothic - distutils不要の直接登録方式）
# Python 3.14 で distutils が廃止されたため、japanize_matplotlib をインポートせず
# site-packages 内の ipaexg.ttf を直接登録する。
# ============================================================
import site as _site

_JP_FONT_NAME = None
for _sp in _site.getsitepackages():
    _candidate = Path(_sp) / 'japanize_matplotlib' / 'fonts' / 'ipaexg.ttf'
    if _candidate.exists():
        try:
            _fm.fontManager.addfont(str(_candidate))
            _JP_FONT_NAME = _fm.FontProperties(fname=str(_candidate)).get_name()
        except Exception:
            pass
        break


def _result_to_png(df: pd.DataFrame) -> bytes:
    """集計DataFrameをmatplotlibでPNG画像に変換する"""
    cols = ["馬番", "馬名", "単勝オッズ", "内部勝率(%)", "1着率(%)", "2着率(%)", "3着率(%)", "4着率(%)", "5着率(%)", "平均着順"]
    d = df[cols].copy()
    n = len(d)

    # rc_context で日本語フォントを図内全体に適用（元の設定は自動復元）
    _font_ctx = {'font.family': [_JP_FONT_NAME]} if _JP_FONT_NAME else {}

    with plt.rc_context(_font_ctx):
        fig_h = max(5.0, n * 0.52 + 1.6)
        fig, ax = plt.subplots(figsize=(17, fig_h))
        ax.axis('off')
        fig.patch.set_facecolor('#0d1b2a')

        row_colors = [
            ['#162840'] * len(cols) if i % 2 == 0 else ['#0d2030'] * len(cols)
            for i in range(n)
        ]

        table = ax.table(
            cellText=d.values.tolist(),
            colLabels=cols,
            cellLoc='center',
            loc='center',
            cellColours=row_colors,
            colColours=['#1a3a5c'] * len(cols),
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.9)

        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor('#1e3a5f')
            if row == 0:
                cell.get_text().set_color('#ffd700')
                cell.get_text().set_fontweight('bold')
            else:
                cell.get_text().set_color('#e8e8e8')

        plt.title("スタホ4 シミュレーター 集計結果",
                  color='#ffd700', fontsize=14, pad=14)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                    facecolor='#0d1b2a', edgecolor='none')
        plt.close(fig)
    buf.seek(0)
    return buf.read()

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="スタホ4風 競馬シミュレーター",
    page_icon="🐎",
    layout="wide",
)

# ============================================================
# 読み込みペンディング処理
# （ウィジェットが描画される前にセッションステートを更新する）
# ============================================================
if "_pending_load" in st.session_state:
    _pending_horses = st.session_state.pop("_pending_load")
    _pending_sources = st.session_state.pop("_pending_sources", [False] * len(_pending_horses))
    for i, (n, o) in enumerate(_pending_horses):
        st.session_state[f"eff_name_{i}"] = n          # 実効名を更新
        st.session_state[f"odds_{i}"] = float(o)       # オッズを更新
        st.session_state[f"name_input_{i}"] = ""       # 入力欄をクリア（placeholderに反映）
        st.session_state[f"is_player_{i}"] = bool(_pending_sources[i]) if i < len(_pending_sources) else False
    st.session_state["added_horse_count"] = sum(1 for i in range(14) if st.session_state.get(f"is_player_{i}", False))

if "_pending_player_slots" in st.session_state:
    _slots = st.session_state.pop("_pending_player_slots")
    for i in range(5):
        if i < len(_slots):
            n, o = _slots[i]
            st.session_state[f"_bulk_name_{i}"] = str(n)
            st.session_state[f"_bulk_odds_{i}"] = float(o)
        else:
            st.session_state[f"_bulk_name_{i}"] = ""
            st.session_state[f"_bulk_odds_{i}"] = 10.0

# ============================================================
# カスタムCSS（スタホっぽい雰囲気）
# ============================================================
st.markdown("""
<style>
    /* 全体背景 */
    .stApp { background-color: #0d1b2a; color: #e8e8e8; }

    /* メインタイトル */
    .main-title {
        text-align: center;
        font-size: 2.4rem;
        font-weight: bold;
        color: #ffd700;
        text-shadow: 0 0 20px #ff8c00, 0 0 40px #ff4500;
        letter-spacing: 4px;
        padding: 10px 0 4px;
    }
    .sub-title {
        text-align: center;
        font-size: 1.0rem;
        color: #aaa;
        margin-bottom: 20px;
        letter-spacing: 2px;
    }

    /* サイドバー */
    section[data-testid="stSidebar"] {
        background-color: #f4f6fb;
        border-right: 2px solid #cdd5e0;
    }
    section[data-testid="stSidebar"] * { color: #111111 !important; }

    /* メトリクスカード */
    [data-testid="metric-container"] {
        background-color: #162840;
        border: 1px solid #1e4a7a;
        border-radius: 8px;
        padding: 8px 14px;
    }
    [data-testid="metric-container"] label { color: #88aacc !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #ffd700 !important;
        font-size: 1.5rem !important;
        font-weight: bold !important;
    }

    /* テーブル */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* ボタン */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #c8860a, #e6a800);
        color: #0d1b2a;
        font-size: 1.1rem;
        font-weight: bold;
        border: none;
        border-radius: 8px;
        padding: 12px;
        letter-spacing: 2px;
        cursor: pointer;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.85; }

    /* タブ */
    button[data-baseweb="tab"] {
        color: #aac8e8 !important;
        font-weight: bold;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #ffd700 !important;
        border-bottom: 2px solid #ffd700 !important;
    }

    /* 区切り線 */
    hr { border-color: #1e3a5f; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# タイトル
# ============================================================
st.markdown('<div class="main-title">🐎 STAR HORSE 4 SIMULATOR 🏆</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">単勝オッズ ベース レースシミュレーター</div>', unsafe_allow_html=True)
st.markdown("---")

# ============================================================
# デフォルトの馬データ
# ============================================================
DEFAULT_HORSES = [
    ("シガー",                 2.0),
    ("スキップアウェイ",       2.7),
    ("アンブライドルド",       9.6),
    ("プレザントタップ",      12.7),
    ("ベーレンズ",            13.3),
    ("コロナドズクエスト",    34.6),
    ("コンサーン",            43.4),
    ("キャットシーフ",        54.3),
    ("デヴィルヒズデュー",    58.5),
    ("コロニアルアッフェアー", 75.8),
    ("ストライクザゴールド",  82.2),
    ("サンダーランブル",     143.0),
    ("キッシンクリス",       156.0),
    ("エクトンパーク",       168.0),
]

# 馬名の実効値をセッションステートで管理（初回のみデフォルト値で初期化）
for _i, (_dname, _) in enumerate(DEFAULT_HORSES):
    st.session_state.setdefault(f"eff_name_{_i}", _dname)
    st.session_state.setdefault(f"odds_{_i}", float(DEFAULT_HORSES[_i][1]))
    st.session_state.setdefault(f"is_player_{_i}", False)
st.session_state.setdefault("added_horse_count", 0)  # ユーザー追加済み馬数
st.session_state.setdefault("player_registration_done", False)
st.session_state.setdefault("show_adjusted_odds_view", False)

# ============================================================
# サイドバー: 入力フォーム
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ レース設定")
    st.markdown("---")

    # 試行回数
    num_simulations = st.select_slider(
        "🔄 シミュレーション回数",
        options=[1_000, 5_000, 10_000, 30_000, 50_000, 100_000],
        value=10_000,
        help="回数が多いほど統計が安定しますが時間がかかります",
    )

    st.markdown("---")
    st.markdown("### 🐎 馬名 ＆ 単勝オッズ")
    st.caption("オッズを変更して「シミュレーション開始」を押してください")

    # 馬ごとの入力欄
    # ・value="" で空欄スタート → 入力済みの文字を消す手間が不要
    # ・placeholder に現在の有効な馬名を表示（ヒントとして）
    # ・何も入力せずに離れると eff_name が維持される（元の名前を復元）
    horse_inputs = []
    for i, (name, odds) in enumerate(DEFAULT_HORSES):
        col1, col2 = st.columns([2, 1])
        with col1:
            h_name_raw = st.text_input(
                f"馬{i+1}",
                value="",
                placeholder=st.session_state.get(f"eff_name_{i}", name),
                key=f"name_input_{i}",
                label_visibility="collapsed",
            )
            if h_name_raw.strip():
                st.session_state[f"eff_name_{i}"] = h_name_raw.strip()
            effective_name = st.session_state[f"eff_name_{i}"]
        with col2:
            h_odds = st.number_input(
                f"odds_{i}",
                min_value=1.0,
                max_value=999.9,
                step=0.1,
                format="%.1f",
                key=f"odds_{i}",
                label_visibility="collapsed",
            )
        horse_inputs.append((effective_name, h_odds))

    # ── 設定の保存・読み込み ──────────────────────────────
    st.markdown("---")
    st.markdown("### 💾 プリセット管理")

    # 保存
    save_name = st.text_input(
        "プリセット名",
        placeholder="例: 決勝レース",
        key="_save_name",
        label_visibility="visible",
    )
    if st.button("💾 現在の設定を保存"):
        if save_name.strip():
            current_data = [
                (st.session_state.get(f"eff_name_{i}", DEFAULT_HORSES[i][0]),
                 float(st.session_state.get(f"odds_{i}", DEFAULT_HORSES[i][1])))
                for i in range(14)
            ]
            _save_config(save_name.strip(), current_data)
            st.success(f"「{save_name.strip()}」を保存しました！")
        else:
            st.warning("プリセット名を入力してください")

    # 読み込み・削除
    all_configs = _load_all_configs()
    race_configs = {k: v for k, v in all_configs.items() if k != PLAYER_PRESET_KEY}
    if race_configs:
        st.markdown("")
        selected_preset = st.selectbox(
            "保存済みプリセット",
            list(race_configs.keys()),
            key="_config_select",
        )
        col_load, col_del = st.columns(2)
        with col_load:
            if st.button("📂 読み込み", key="_btn_load"):
                st.session_state["_pending_load"] = race_configs[selected_preset]
                st.session_state["_pending_sources"] = [False] * 14
                st.session_state["added_horse_count"] = 0
                st.session_state["player_registration_done"] = False
                st.session_state["show_adjusted_odds_view"] = False
                st.session_state.pop("_last_odds_view", None)
                st.rerun()
        with col_del:
            if st.button("🗑️ 削除", key="_btn_delete"):
                _delete_config(selected_preset)
                st.rerun()
    else:
        st.caption("保存済みプリセットはありません")

    # ── プレイヤー馬登録（5頭一括） ──────────────────────────
    st.markdown("---")
    st.markdown("### ➕ プレイヤー馬登録（最大5頭）")
    _added_count = sum(1 for i in range(14) if st.session_state.get(f"is_player_{i}", False))
    registration_done = st.session_state.get("player_registration_done", False)
    st.caption(
        "5枠に入力した馬を一括登録します。登録後は追加登録できません（リセットで再登録可能）"
    )

    st.markdown("#### 💾 プレイヤー登録枠の保存")
    player_preset_name = st.text_input(
        "プレイヤー登録プリセット名",
        placeholder="例: 先行型5頭",
        key="_player_preset_name",
        label_visibility="collapsed",
        disabled=registration_done,
    )

    col_psave, col_pload, col_pdel = st.columns(3)
    with col_psave:
        if st.button("💾 枠を保存", key="_btn_player_save", disabled=registration_done):
            if player_preset_name.strip():
                slots = [
                    (st.session_state.get(f"_bulk_name_{i}", "").strip(), float(st.session_state.get(f"_bulk_odds_{i}", 10.0)))
                    for i in range(5)
                ]
                _save_player_preset(player_preset_name.strip(), slots)
                st.success(f"プレイヤー枠「{player_preset_name.strip()}」を保存しました")
            else:
                st.warning("プレイヤー登録プリセット名を入力してください")

    player_presets = _load_player_presets()
    _player_preset_names = list(player_presets.keys())
    selected_player_preset = None
    if _player_preset_names:
        selected_player_preset = st.selectbox(
            "プレイヤー枠プリセット",
            _player_preset_names,
            key="_player_preset_select",
            disabled=registration_done,
        )
    else:
        st.caption("プレイヤー枠プリセットはありません")

    with col_pload:
        if st.button("📂 枠を読み込み", key="_btn_player_load", disabled=registration_done or not _player_preset_names):
            st.session_state["_pending_player_slots"] = player_presets[selected_player_preset]
            st.rerun()

    with col_pdel:
        if st.button("🗑️ 枠を削除", key="_btn_player_del", disabled=registration_done or not _player_preset_names):
            _delete_player_preset(selected_player_preset)
            st.rerun()

    for slot in range(5):
        col_n, col_o = st.columns([2, 1])
        with col_n:
            st.text_input(
                f"登録枠{slot + 1} 馬名",
                placeholder="馬名を入力",
                key=f"_bulk_name_{slot}",
                label_visibility="collapsed",
                disabled=registration_done,
            )
        with col_o:
            st.number_input(
                f"登録枠{slot + 1} オッズ",
                min_value=1.0,
                max_value=999.9,
                value=10.0,
                step=0.1,
                format="%.1f",
                key=f"_bulk_odds_{slot}",
                label_visibility="collapsed",
                disabled=registration_done,
            )

    if registration_done:
        st.warning("プレイヤー馬は登録済みです。追加登録はできません。再登録する場合はリセットしてください。")

    col_reg, col_rst = st.columns(2)
    with col_reg:
        register_clicked = st.button("✅ 5枠を登録して再計算", key="_btn_bulk_register", disabled=registration_done)
    with col_rst:
        reset_clicked = st.button("🔄 追加馬をリセット", key="_btn_reset_horses", disabled=(_added_count == 0 and not registration_done))

    if reset_clicked:
        st.session_state["added_horse_count"] = 0
        st.session_state["player_registration_done"] = False
        st.session_state["show_adjusted_odds_view"] = False
        st.session_state.pop("_last_odds_view", None)
        st.session_state["_pending_load"] = list(DEFAULT_HORSES)
        st.session_state["_pending_sources"] = [False] * 14
        st.session_state["_pending_player_slots"] = [("", 10.0) for _ in range(5)]
        st.rerun()

    if register_clicked:
        entries = []
        for slot in range(5):
            name = st.session_state.get(f"_bulk_name_{slot}", "").strip()
            odds = float(st.session_state.get(f"_bulk_odds_{slot}", 10.0))
            if name:
                entries.append({"name": name, "odds": odds})

        if not entries:
            st.warning("登録する馬名を1頭以上入力してください")
        else:
            old_horses_snapshot = list(horse_inputs)
            current_14 = [
                {
                    "name": horse_inputs[i][0],
                    "odds": float(horse_inputs[i][1]),
                    "is_player": bool(st.session_state.get(f"is_player_{i}", False)),
                }
                for i in range(14)
            ]

            _WIN_CAP = 0.805
            O14 = sum(1.0 / h["odds"] for h in current_14)

            # 入力順依存をなくすため、5枠を同時投入して一括で除外・再計算する
            merged = current_14 + [{"name": e["name"], "odds": float(e["odds"]), "is_player": True} for e in entries]

            # 頭数が14になるまで、CPU馬を優先して最下位人気（最大オッズ）から除外
            while len(merged) > 14:
                cpu_candidates = [i for i, h in enumerate(merged) if not h["is_player"]]
                candidate_idx = cpu_candidates if cpu_candidates else list(range(len(merged)))
                remove_idx = max(candidate_idx, key=lambda i: merged[i]["odds"])
                merged.pop(remove_idx)

            remaining = merged

            # 上限方式:
            # - プレイヤー合計勝率が80.5%を超えた場合のみ、80.5:19.5に圧縮
            # - 未満の場合はプレイヤー側は据え置き、CPU側のみ再計算
            total_inv_before = sum(1.0 / h["odds"] for h in remaining)
            player_inv_before = sum(1.0 / h["odds"] for h in remaining if h["is_player"])
            cpu_inv_before = sum(1.0 / h["odds"] for h in remaining if not h["is_player"])
            player_share_before = (player_inv_before / total_inv_before) if total_inv_before > 0 else 0.0
            player_rebalanced = False
            any_input_adjusted = False

            if player_share_before > _WIN_CAP:
                target_player_inv = _WIN_CAP * O14
                target_cpu_inv = (1.0 - _WIN_CAP) * O14
                player_rebalanced = True
                any_input_adjusted = True
            else:
                target_player_inv = player_inv_before
                target_cpu_inv = O14 - target_player_inv

            scale_player = (player_inv_before / target_player_inv) if (player_inv_before > 0 and target_player_inv > 0) else 1.0
            scale_cpu = (cpu_inv_before / target_cpu_inv) if (cpu_inv_before > 0 and target_cpu_inv > 0) else 1.0

            for h in remaining:
                if h["is_player"]:
                    h["odds"] = max(1.0, round(h["odds"] * scale_player, 1))
                else:
                    h["odds"] = max(1.1, round(h["odds"] * scale_cpu, 1))

            # 最終安全弁: 丸め/166補正後にプレイヤー合計勝率が上限を超えていたら再圧縮
            # target_player_inv / (target_player_inv + cpu_inv_fixed) = _WIN_CAP
            # -> target_player_inv = (_WIN_CAP / (1 - _WIN_CAP)) * cpu_inv_fixed
            for _ in range(3):
                player_inv_now = sum(1.0 / h["odds"] for h in remaining if h["is_player"])
                cpu_inv_fixed = sum(1.0 / h["odds"] for h in remaining if not h["is_player"])
                total_inv_now = player_inv_now + cpu_inv_fixed
                player_share_now = (player_inv_now / total_inv_now) if total_inv_now > 0 else 0.0
                if player_share_now <= _WIN_CAP or player_inv_now <= 0 or cpu_inv_fixed <= 0:
                    break

                target_player_inv_now = (_WIN_CAP / (1.0 - _WIN_CAP)) * cpu_inv_fixed
                if target_player_inv_now <= 0:
                    break
                scale_player_cap = player_inv_now / target_player_inv_now

                for h in remaining:
                    if h["is_player"]:
                        h["odds"] = max(1.0, round(h["odds"] * scale_player_cap, 1))

                player_rebalanced = True
                any_input_adjusted = True

            # 表示オッズの土台（オーバーラウンド）を初期O14に戻す
            # これを行わないと表示が「期待勝率そのもののオッズ（フェアオッズ）」寄りになる
            total_inv_final = sum(1.0 / h["odds"] for h in remaining)
            if total_inv_final > 0 and O14 > 0:
                scale_all = total_inv_final / O14
                if abs(scale_all - 1.0) > 1e-9:
                    for h in remaining:
                        if h["is_player"]:
                            h["odds"] = max(1.0, round(h["odds"] * scale_all, 1))
                        else:
                            h["odds"] = max(1.1, round(h["odds"] * scale_all, 1))

            # 最終オッズとして166倍制約を適用（内部計算・期待勝率計算にもこの値を使用）
            # 166倍超のCPU馬が複数いる場合は 166, 164, 162... と2倍刻みにする
            capped_cpu = [
                (i, h["odds"])
                for i, h in enumerate(remaining)
                if (not h["is_player"] and h["odds"] >= 166.0)
            ]
            capped_cpu.sort(key=lambda x: x[1], reverse=True)
            for rank, (idx, _) in enumerate(capped_cpu):
                remaining[idx]["odds"] = max(1.1, 166.0 - 2.0 * rank)

            next_14 = []
            for h in remaining:
                new_o = h["odds"]
                next_14.append({"name": h["name"], "odds": new_o, "is_player": bool(h["is_player"])})

            new_horse_list = [(h["name"], h["odds"]) for h in next_14]
            new_source_flags = [bool(h["is_player"]) for h in next_14]
            st.session_state["added_horse_count"] = sum(1 for flag in new_source_flags if flag)
            st.session_state["player_registration_done"] = True

            st.session_state["_add_horse_msg"] = {
                "mode": "bulk",
                "registered_count": len(entries),
                "registered_names": [e["name"] for e in entries],
                "odds_was_adjusted": any_input_adjusted,
                "player_rebalanced": player_rebalanced,
                "old_horses": old_horses_snapshot,
                "new_horses": new_horse_list,
            }
            st.session_state["_last_odds_view"] = {
                "old_horses": old_horses_snapshot,
                "new_horses": new_horse_list,
            }
            st.session_state["show_adjusted_odds_view"] = True

            # ウィジェット生成後に odds_* を直接更新すると例外になるため、次回 rerun 冒頭で反映
            st.session_state["_pending_load"] = new_horse_list
            st.session_state["_pending_sources"] = new_source_flags
            st.rerun()

    st.markdown("---")
    run_button = st.button("🚀 シミュレーション開始", width="stretch")

# ============================================================
# シミュレーション関数
# ============================================================
def calculate_internal_prob(odds_list):
    inv_odds = np.array([1.0 / o for o in odds_list])
    return inv_odds / inv_odds.sum()


def simulate_race(probs):
    """1レース分の着順をループ再正規化方式で決定する"""
    num_horses = len(probs)
    remaining_indices = list(range(num_horses))
    remaining_probs = probs.copy()
    finish_order = np.zeros(num_horses, dtype=int)

    for rank in range(1, num_horses + 1):
        norm_probs = remaining_probs / remaining_probs.sum()
        chosen = np.random.choice(remaining_indices, p=norm_probs)
        finish_order[chosen] = rank
        idx = remaining_indices.index(chosen)
        remaining_indices.pop(idx)
        remaining_probs = np.delete(remaining_probs, idx)

    return finish_order


def run_simulation(horse_names, odds_list, num_simulations):
    n = len(horse_names)
    probs = calculate_internal_prob(odds_list)

    win_counts    = np.zeros(n, dtype=int)
    place2_counts = np.zeros(n, dtype=int)
    place3_counts = np.zeros(n, dtype=int)
    place4_counts = np.zeros(n, dtype=int)
    place5_counts = np.zeros(n, dtype=int)
    rank_sum      = np.zeros(n, dtype=float)

    # バッチ実行でプログレスバーを更新
    batch = max(1, num_simulations // 100)
    progress = st.progress(0, text="シミュレーション実行中...")

    for i in range(num_simulations):
        fo = simulate_race(probs)
        win_counts    += (fo == 1).astype(int)
        place2_counts += (fo == 2).astype(int)
        place3_counts += (fo == 3).astype(int)
        place4_counts += (fo == 4).astype(int)
        place5_counts += (fo == 5).astype(int)
        rank_sum      += fo

        if (i + 1) % batch == 0:
            pct = (i + 1) / num_simulations
            progress.progress(pct, text=f"シミュレーション実行中... {i+1:,}/{num_simulations:,}回")

    progress.progress(1.0, text="完了！")

    df = pd.DataFrame({
        "馬番": range(1, n + 1),
        "馬名": horse_names,
        "単勝オッズ": [f"{o:.1f}倍" for o in odds_list],
        "内部勝率(%)": (probs * 100).round(2),
        "1着回数": win_counts,
        "1着率(%)": (win_counts / num_simulations * 100).round(2),
        "2着回数": place2_counts,
        "2着率(%)": (place2_counts / num_simulations * 100).round(2),
        "3着回数": place3_counts,
        "3着率(%)": (place3_counts / num_simulations * 100).round(2),
        "4着回数": place4_counts,
        "4着率(%)": (place4_counts / num_simulations * 100).round(2),
        "5着回数": place5_counts,
        "5着率(%)": (place5_counts / num_simulations * 100).round(2),
        "平均着順": (rank_sum / num_simulations).round(2),
    })
    return df, probs


# ============================================================
# 馬追加の結果通知
# ============================================================
if "_add_horse_msg" in st.session_state:
    msg = st.session_state.pop("_add_horse_msg")
    if msg.get("mode") == "bulk":
        st.success(
            f"✅ プレイヤー馬を {msg['registered_count']} 頭登録しました。"
            f"（{', '.join(msg['registered_names'])}）"
        )
        if msg.get("odds_was_adjusted"):
            st.info("⚠️ プレイヤー合計勝率が80.5%を超えたため、上限に合わせて自動調整しました。")
        if msg.get("player_rebalanced"):
            st.info("⚖️ プレイヤー側80.5%・CPU側19.5%になるよう再計算しました。")
    else:
        if msg["added_was_removed"]:
            st.warning(
                f"⚠️ 追加した **{msg['added_name']}**（{msg['added_odds']:.1f}倍）は"
                f"最下位人気のため除外対象となりました。変更はありません。"
            )
        else:
            st.success(
                f"✅ **{msg['added_name']}**（{msg['added_odds']:.1f}倍）を追加。"
                f"最下位人気 **{msg['removed_name']}**（{msg['removed_odds']:.1f}倍）を除外し、"
                f"各馬のオッズを再計算しました。"
            )
            if msg.get("odds_was_adjusted"):
                st.info(
                    f"⚠️ 入力オッズ {msg['original_input_odds']:.1f}倍 → "
                    f"**{msg['added_odds']:.1f}倍** に自動調整しました（追加馬の内部勝率上限: 80.5%）"
                )
            if msg.get("player_rebalanced"):
                st.info(
                    f"⚖️ プレイヤー馬の内部勝率合計が上限超過のため、"
                    f"プレイヤー馬同士で再計算しました（{msg['player_share_before']*100:.1f}% → {msg['player_share_after']*100:.1f}%）"
                )
        old_dict = {name: o for name, o in msg["old_horses"]}
        rows = []
        for name, new_o in msg["new_horses"]:
            old_o = old_dict.get(name)
            if old_o is None:
                rows.append({"馬名": name, "変更前": "—（新規）", "変更後": f"{new_o:.1f}倍", "変動": "新規追加"})
            else:
                diff = new_o - old_o
                sign = "+" if diff > 0 else ""
                rows.append({"馬名": name, "変更前": f"{old_o:.1f}倍", "変更後": f"{new_o:.1f}倍", "変動": f"{sign}{diff:.1f}"})
        comp_df = pd.DataFrame(rows)
        st.dataframe(comp_df, hide_index=True, use_container_width=True, height=530)
    st.markdown("---")

# ============================================================
# 結果表示
# ============================================================
if run_button:
    horse_names = [h[0] for h in horse_inputs]
    odds_list   = [h[1] for h in horse_inputs]

    result_df, probs = run_simulation(horse_names, odds_list, num_simulations)

    # ── サマリーメトリクス ──────────────────────────────────
    st.markdown("### 📊 シミュレーション結果")

    top1 = result_df.loc[result_df["1着率(%)"].idxmax()]
    overround = sum(1 / o for o in odds_list) * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏆 最多1着馬", top1["馬名"])
    col2.metric("📈 最多1着率", f"{top1['1着率(%)']:.2f}%")
    col3.metric("🎯 オーバーラウンド", f"{overround:.1f}%")
    col4.metric("🔄 試行回数", f"{num_simulations:,}回")

    st.markdown("---")

    # ── タブ: 表 / グラフ ──────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📋 集計テーブル", "📊 着率グラフ", "🔢 内部勝率分布"])

    # ── タブ1: テーブル ──
    with tab1:
        # 1着率順にソート
        display_df = result_df.sort_values("1着率(%)", ascending=False).reset_index(drop=True)
        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            column_config={
                "馬番": st.column_config.NumberColumn("馬番", width="small"),
                "馬名": st.column_config.TextColumn("馬名", width="medium"),
                "単勝オッズ": st.column_config.TextColumn("単勝オッズ", width="small"),
                "内部勝率(%)": st.column_config.ProgressColumn(
                    "内部勝率(%)", format="%.2f%%", min_value=0, max_value=100
                ),
                "1着率(%)": st.column_config.ProgressColumn(
                    "1着率(%)", format="%.2f%%", min_value=0, max_value=100
                ),
                "2着率(%)": st.column_config.ProgressColumn(
                    "2着率(%)", format="%.2f%%", min_value=0, max_value=100
                ),
                "3着率(%)": st.column_config.ProgressColumn(
                    "3着率(%)", format="%.2f%%", min_value=0, max_value=100
                ),
                "4着回数": st.column_config.NumberColumn("4着回数"),
                "4着率(%)": st.column_config.ProgressColumn(
                    "4着率(%)", format="%.2f%%", min_value=0, max_value=100
                ),
                "5着回数": st.column_config.NumberColumn("5着回数"),
                "5着率(%)": st.column_config.ProgressColumn(
                    "5着率(%)", format="%.2f%%", min_value=0, max_value=100
                ),
                "平均着順": st.column_config.NumberColumn("平均着順", format="%.2f"),
            },
            height=560,
        )

        # ── ダウンロードボタン ──────────────────────────────
        st.markdown("")
        dl1, dl2, _ = st.columns([1, 1, 4])
        with dl1:
            csv_bytes = display_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label=":material/download: CSV 保存",
                data=csv_bytes,
                file_name="simulation_result.csv",
                mime="text/csv",
                key="dl_csv",
            )
        with dl2:
            png_bytes = _result_to_png(display_df)
            st.download_button(
                label=":material/image: 画像 保存",
                data=png_bytes,
                file_name="simulation_result.png",
                mime="image/png",
                key="dl_png",
            )

    # ── タブ2: 着率グラフ（棒グラフ）──
    with tab2:
        names    = result_df["馬名"].tolist()
        win_rate = result_df["1着率(%)"].tolist()
        p2_rate  = result_df["2着率(%)"].tolist()
        p3_rate  = result_df["3着率(%)"].tolist()
        p4_rate  = result_df["4着率(%)"].tolist()
        p5_rate  = result_df["5着率(%)"].tolist()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="1着率", x=names, y=win_rate,
            marker_color="#ffd700",
            text=[f"{v:.1f}%" for v in win_rate],
            textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name="2着率", x=names, y=p2_rate,
            marker_color="#4fc3f7",
            text=[f"{v:.1f}%" for v in p2_rate],
            textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name="3着率", x=names, y=p3_rate,
            marker_color="#81c784",
            text=[f"{v:.1f}%" for v in p3_rate],
            textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name="4着率", x=names, y=p4_rate,
            marker_color="#ff8a65",
            text=[f"{v:.1f}%" for v in p4_rate],
            textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name="5着率", x=names, y=p5_rate,
            marker_color="#ce93d8",
            text=[f"{v:.1f}%" for v in p5_rate],
            textposition="outside",
        ))
        fig.update_layout(
            barmode="group",
            plot_bgcolor="#0d1b2a",
            paper_bgcolor="#0d1b2a",
            font=dict(color="#e8e8e8"),
            xaxis=dict(
                tickfont=dict(size=11),
                gridcolor="#1e3a5f",
            ),
            yaxis=dict(
                title="着率（%）",
                gridcolor="#1e3a5f",
            ),
            legend=dict(
                bgcolor="#122036",
                bordercolor="#1e4a7a",
                borderwidth=1,
            ),
            title=dict(
                text="各馬の1〜5着率",
                font=dict(size=16, color="#ffd700"),
            ),
            margin=dict(t=60, b=20),
            height=480,
        )
        st.plotly_chart(fig, width="stretch")

    # ── タブ3: 内部勝率の円グラフ ──
    with tab3:
        fig2 = go.Figure(go.Pie(
            labels=names,
            values=result_df["内部勝率(%)"].tolist(),
            hole=0.45,
            textinfo="label+percent",
            textfont=dict(size=12),
            marker=dict(
                colors=px.colors.qualitative.Bold,
                line=dict(color="#0d1b2a", width=2),
            ),
        ))
        fig2.add_annotation(
            text="内部勝率",
            x=0.5, y=0.5,
            font=dict(size=16, color="#ffd700"),
            showarrow=False,
        )
        fig2.update_layout(
            plot_bgcolor="#0d1b2a",
            paper_bgcolor="#0d1b2a",
            font=dict(color="#e8e8e8"),
            title=dict(
                text="各馬の内部勝率分布（正規化済み）",
                font=dict(size=16, color="#ffd700"),
            ),
            legend=dict(
                bgcolor="#122036",
                bordercolor="#1e4a7a",
                borderwidth=1,
                font=dict(size=11),
            ),
            height=520,
        )
        st.plotly_chart(fig2, width="stretch")

        st.info(
            f"**オーバーラウンドについて**: "
            f"オッズ逆数の合計は {overround:.1f}% です。"
            f"これが100%を超えている分（{overround-100:.1f}%）がゲーム側の控除率です。"
            f"シミュレーターはこの控除分を除いて全馬の勝率合計が100%になるよう正規化しています。"
        )

elif st.session_state.get("show_adjusted_odds_view") and "_last_odds_view" in st.session_state:
    st.markdown("### 🧾 オッズ再計算結果")
    _last = st.session_state["_last_odds_view"]
    old_dict = {name: o for name, o in _last["old_horses"]}
    rows = []
    for name, new_o in _last["new_horses"]:
        old_o = old_dict.get(name)
        if old_o is None:
            rows.append({"馬名": name, "変更前": "—（新規）", "変更後": f"{new_o:.1f}倍", "変動": "新規追加"})
        else:
            diff = new_o - old_o
            sign = "+" if diff > 0 else ""
            rows.append({"馬名": name, "変更前": f"{old_o:.1f}倍", "変更後": f"{new_o:.1f}倍", "変動": f"{sign}{diff:.1f}"})
    comp_df = pd.DataFrame(rows)
    st.dataframe(comp_df, hide_index=True, use_container_width=True, height=530)

else:
    # 起動直後のガイド画面
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #88aacc;">
        <div style="font-size:4rem;">🏇</div>
        <h2 style="color:#ffd700; letter-spacing:3px;">使い方</h2>
        <ol style="display:inline-block; text-align:left; font-size:1.05rem; line-height:2.2;">
            <li>左のサイドバーで <b style="color:#ffd700;">馬名</b> と <b style="color:#ffd700;">単勝オッズ</b> を設定</li>
            <li><b style="color:#ffd700;">シミュレーション回数</b> を選択（多いほど精度UP）</li>
            <li>「<b style="color:#e6a800;">🚀 シミュレーション開始</b>」を押す</li>
            <li>集計テーブル・グラフで結果を確認！</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
