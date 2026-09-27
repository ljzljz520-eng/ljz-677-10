#!/usr/bin/env python3
"""生成演示用导入文件 sample_data.csv（城东镇）与导入模板 template.csv。

数据设计（一次演示覆盖全部功能）：
  - 34 条完全合法 -> 平台受理成功
  - 3 条银行卡尾号 00 -> 平台退回：账户已销户
  - 2 条银行卡尾号 99 -> 平台退回：账户冻结
  - 2 条金额 25000 元 -> 通过系统校验（<5万），被平台退回：超单笔限额2万
  - 1 条姓名含“测” -> 平台退回：户名不符
  - 7 条格式错误（身份证校验码错/位数错、银行卡错、金额3位小数、负数、乡镇不符、姓名空）
  - 2 条与文件内前面记录身份证重复
"""
import csv
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from subsidy.validators import ID_WEIGHTS, ID_CHECK_CODES

random.seed(20260927)

SURNAMES = "张王李赵刘陈杨黄周吴徐孙马朱胡郭何罗"
GIVEN = ["伟", "芳", "娜", "敏", "静", "磊", "军", "洋", "勇", "艳", "杰", "涛",
         "明", "超", "秀英", "霞", "平", "刚", "桂英", "建国", "玉兰", "志强"]


def make_id_card(seq3):
    """生成通过校验码的身份证号。area=341322 birth 随机。"""
    year = random.randint(1955, 2000)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    base = "341322%04d%02d%02d%03d" % (year, month, day, seq3)
    total = sum(int(base[i]) * ID_WEIGHTS[i] for i in range(17))
    return base + ID_CHECK_CODES[total % 11]


def luhn_check_digit(body):
    total = 0
    for i, ch in enumerate(reversed(body + "0")):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def make_bank_card(suffix=""):
    """生成通过 Luhn 校验的 16 位卡号；suffix 指定完整卡号结尾（循环至校验位匹配）。"""
    while True:
        n_mid = 15 - 6 - (len(suffix) - 1 if suffix else 0)
        body = "622202" + "".join(random.choice("0123456789") for _ in range(n_mid))
        if suffix:
            body += suffix[:-1]
        check = luhn_check_digit(body)
        if not suffix or check == suffix[-1]:
            return body + check


def person(i):
    return random.choice(SURNAMES) + random.choice(GIVEN) + (random.choice(GIVEN) if i % 3 == 0 else "")


def main():
    rows = []  # (name, id_card, bank_card, amount, township)

    # 34 条完全合法
    used_seq = set()
    for i in range(34):
        seq = 100 + i
        used_seq.add(seq)
        rows.append((person(i), make_id_card(seq), make_bank_card(),
                     "%d.%02d" % (random.randint(300, 8000), random.randint(0, 99)), "城东镇"))

    # 3 条尾号 00（平台退回：销户）
    for i in range(3):
        rows.append((person(40 + i), make_id_card(140 + i), make_bank_card("00"),
                     "%d.00" % random.randint(500, 3000), "城东镇"))

    # 2 条尾号 99（平台退回：冻结）
    for i in range(2):
        rows.append((person(50 + i), make_id_card(150 + i), make_bank_card("99"),
                     "%d.00" % random.randint(500, 3000), "城东镇"))

    # 2 条金额 25000（平台退回：超限额）
    for i in range(2):
        rows.append((person(60 + i), make_id_card(160 + i), make_bank_card(),
                     "25000.00", "城东镇"))

    # 1 条姓名含“测”（平台退回：户名不符）
    rows.append(("李测试", make_id_card(170), make_bank_card(), "1200.00", "城东镇"))

    # ---- 以下 42 条为合法记录，上送后 34 成功 / 8 退回，分 3 批（20+20+2）----

    # 格式错误：身份证校验码错（合法号改末位）
    bad_id = make_id_card(180)
    bad_id = bad_id[:-1] + ("0" if bad_id[-1] != "0" else "1")
    rows.append((person(80), bad_id, make_bank_card(), "800.00", "城东镇"))
    # 身份证 15 位
    rows.append((person(81), "341322900101123", make_bank_card(), "800.00", "城东镇"))
    # 银行卡 Luhn 错
    rows.append((person(82), make_id_card(181), "6222021234567890123", "800.00", "城东镇"))
    # 金额 3 位小数
    rows.append((person(83), make_id_card(182), make_bank_card(), "100.123", "城东镇"))
    # 金额负数
    rows.append((person(84), make_id_card(183), make_bank_card(), "-50.00", "城东镇"))
    # 乡镇不符
    rows.append((person(85), make_id_card(184), make_bank_card(), "800.00", "城西镇"))
    # 姓名为空
    rows.append(("", make_id_card(185), make_bank_card(), "800.00", "城东镇"))

    # 2 条与文件内第 2、3 行身份证重复
    rows.append((person(90), rows[1][1], make_bank_card(), "900.00", "城东镇"))
    rows.append((person(91), rows[2][1], make_bank_card(), "900.00", "城东镇"))

    out = os.path.join(os.path.dirname(__file__), "..", "sample_data.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["补贴对象", "身份证号", "银行卡号", "金额", "乡镇"])
        w.writerows(rows)
    print("生成 %s，共 %d 行（合法 42 / 格式错误 7 / 重复 2）" % (out, len(rows)))

    # 导入模板（表头 + 1 行合法示例）
    tpl = os.path.join(os.path.dirname(__file__), "..", "template.csv")
    with open(tpl, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["补贴对象", "身份证号", "银行卡号", "金额", "乡镇"])
        w.writerow(["张三", make_id_card(999), make_bank_card(), "1500.00", "城东镇"])
    print("生成 %s" % tpl)


if __name__ == "__main__":
    main()
