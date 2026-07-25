"""
スターホース4風 競馬レース結果シミュレーター
========================================
単勝オッズをベースに、14頭立てレースの着順をシミュレーションするツールです。
"""

import numpy as np
import pandas as pd

# ============================================================
# ★ここを変更してください: 馬のデータ設定
# ============================================================

# 試行回数（多いほど統計が安定します）
NUM_SIMULATIONS = 10_000

# 馬名と単勝オッズのリスト（ゲーム内の表示オッズを入力）
# 形式: (馬名, 単勝オッズ)
HORSE_DATA = [
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

# ============================================================
# シミュレーション本体
# ============================================================

def calculate_internal_prob(odds_list: list[float]) -> np.ndarray:
    """
    単勝オッズから内部勝率（正規化済み確率）を計算する。

    手順:
      1. 各オッズの逆数を計算 (1 / odds)
      2. 逆数の合計を出す（オーバーラウンド分が含まれる）
      3. 各逆数を合計で割って正規化 → 合計が1.0になる内部勝率
    """
    inv_odds = np.array([1.0 / o for o in odds_list])
    total_inv = inv_odds.sum()
    probs = inv_odds / total_inv
    return probs


def simulate_race(probs: np.ndarray) -> np.ndarray:
    """
    1レース分の着順を決定する。

    ロジック:
      - 残馬の内部勝率の比率を維持しながら、1頭ずつ順番に選出する。
      - numpy の random.choice + replace=False では確率の再正規化が
        行われないため、ループで再計算する方式を採用。

    Parameters
    ----------
    probs : np.ndarray
        正規化済みの内部勝率（合計=1.0）

    Returns
    -------
    np.ndarray
        各馬の着順（0始まりのインデックスに対応）
        例: result[2] = 1 → 2番インデックスの馬が1着
    """
    num_horses = len(probs)
    remaining_indices = list(range(num_horses))
    remaining_probs = probs.copy()
    finish_order = np.zeros(num_horses, dtype=int)

    for rank in range(1, num_horses + 1):
        # 残馬の確率を正規化して次の着順馬を選ぶ
        norm_probs = remaining_probs / remaining_probs.sum()
        chosen = np.random.choice(remaining_indices, p=norm_probs)

        # 選ばれた馬の着順を記録
        finish_order[chosen] = rank

        # 選ばれた馬を候補から除外
        idx_in_remaining = remaining_indices.index(chosen)
        remaining_indices.pop(idx_in_remaining)
        remaining_probs = np.delete(remaining_probs, idx_in_remaining)

    return finish_order


def run_simulation(horse_names: list[str],
                   odds_list: list[float],
                   num_simulations: int) -> pd.DataFrame:
    """
    指定回数シミュレーションを実行し、結果を集計したDataFrameを返す。

    Parameters
    ----------
    horse_names    : 馬名リスト
    odds_list      : 単勝オッズリスト
    num_simulations: 試行回数

    Returns
    -------
    pd.DataFrame : 集計結果テーブル
    """
    num_horses = len(horse_names)
    probs = calculate_internal_prob(odds_list)

    # 集計用配列の初期化
    win_counts   = np.zeros(num_horses, dtype=int)   # 1着回数
    place2_counts = np.zeros(num_horses, dtype=int)  # 2着回数
    place3_counts = np.zeros(num_horses, dtype=int)  # 3着回数
    rank_sum      = np.zeros(num_horses, dtype=float) # 着順合計（平均算出用）

    print(f"シミュレーション実行中... ({num_simulations:,}回)")

    for _ in range(num_simulations):
        finish_order = simulate_race(probs)
        win_cases   = finish_order == 1
        place2_cases = finish_order == 2
        place3_cases = finish_order == 3

        win_counts    += win_cases.astype(int)
        place2_counts += place2_cases.astype(int)
        place3_counts += place3_cases.astype(int)
        rank_sum      += finish_order

    print("完了！\n")

    # DataFrameに集計
    df = pd.DataFrame({
        "馬番": range(1, num_horses + 1),
        "馬名": horse_names,
        "単勝オッズ": odds_list,
        "内部勝率(%)": (probs * 100).round(2),
        "1着回数": win_counts,
        "1着率(%)": (win_counts / num_simulations * 100).round(2),
        "2着回数": place2_counts,
        "2着率(%)": (place2_counts / num_simulations * 100).round(2),
        "3着回数": place3_counts,
        "3着率(%)": (place3_counts / num_simulations * 100).round(2),
        "平均着順": (rank_sum / num_simulations).round(2),
    })

    return df


def print_results(df: pd.DataFrame, num_simulations: int) -> None:
    """
    集計結果を見やすく整形して出力する。
    """
    separator = "=" * 90

    print(separator)
    print(f"  スターホース4風 競馬シミュレーター  ─  試行回数: {num_simulations:,}回")
    print(separator)

    # pandas の表示オプションを調整
    pd.set_option("display.unicode.east_asian_width", True)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", "{:.2f}".format)

    print(df.to_string(index=False))
    print(separator)

    # 補足情報
    total_internal = df["内部勝率(%)"].sum()
    print(f"\n【内部勝率の合計】: {total_internal:.2f}%  "
          f"（オッズのオーバーラウンド控除前の理論合計: "
          f"{sum(1/o for o in df['単勝オッズ'].tolist()) * 100:.2f}%）")

    # 1着率が最も高い馬を表示
    top_horse = df.loc[df["1着率(%)"].idxmax()]
    print(f"\n【最多1着】: {top_horse['馬名']}  "
          f"(1着率 {top_horse['1着率(%)']:.2f}%  /  "
          f"単勝オッズ {top_horse['単勝オッズ']}倍)")
    print()


# ============================================================
# エントリーポイント
# ============================================================

if __name__ == "__main__":
    # 入力データをリストに分解
    horse_names = [h[0] for h in HORSE_DATA]
    odds_list   = [h[1] for h in HORSE_DATA]

    # 入力値の簡易バリデーション
    assert len(horse_names) == 14, "出走頭数は14頭である必要があります"
    assert all(o > 1.0 for o in odds_list), "オッズは1.0より大きい値を入力してください"
    assert NUM_SIMULATIONS > 0, "試行回数は1以上を指定してください"

    # シミュレーション実行
    result_df = run_simulation(horse_names, odds_list, NUM_SIMULATIONS)

    # 結果出力
    print_results(result_df, NUM_SIMULATIONS)
