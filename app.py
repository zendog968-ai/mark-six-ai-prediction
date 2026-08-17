import numpy as np


def generate_filtered_combinations(sorted_probs, n_groups=5):
  # 取出 AI 權重最高的前 25 個號碼作為候選池
  top_pool = [num for num, prob in sorted_probs[:25]]
  valid_combinations = []

  while len(valid_combinations) < n_groups:
    # 從候選池中隨機抽取 6 個不重複的號碼並由小到大排序
    combo = sorted(np.random.choice(top_pool, size=6, replace=False))

    # 計算這 6 個號碼中有幾個奇數
    odd_count = sum(1 for n in combo if n % 2 != 0)

    # 過濾機制：排除 6 碼全奇數或 6 碼全偶數的極端組合
    if odd_count != 0 and odd_count != 6:
      # 確保沒有重複生成相同的組合
      if combo not in valid_combinations:
        valid_combinations.append(combo)

  return valid_combinations