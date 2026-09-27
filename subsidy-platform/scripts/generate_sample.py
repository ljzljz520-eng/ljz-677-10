#!/usr/bin/env python3
"""生成演示用导入文件（含各类正常/异常数据）"""
import csv
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from validators import compute_id_check_code, luhn_check_digit  # noqa: E402

random.seed(20260927)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sample_data')
HEADER = ['姓名', '身份证号', '银行卡号', '发放金额', '乡镇']

SURNAMES = list('张王李赵刘陈杨黄周吴徐孙马朱胡郭何罗高林')
GIVEN = ['伟', '芳', '娜', '敏', '静', '磊', '军', '洋', '勇', '艳',
         '杰', '娟', '涛', '明', '超', '秀英', '建华', '桂兰', '志强', '春梅',
         '国庆', '玉兰', '德福', '翠花', '守财']


def gen_name():
    return random.choice(SURNAMES) + random.choice(GIVEN)


def gen_id_card(region='110101'):
    first17 = '%s%04d%02d%02d%03d' % (
        region, random.randint(1955, 2002), random.randint(1, 12),
        random.randint(1, 28), random.randint(1, 999))
    return first17 + compute_id_check_code(first17)


def gen_bank_card(prefix='622202', total_len=19):
    payload = prefix + ''.join(random.choices('0123456789',
                                              k=total_len - 1 - len(prefix)))
    return payload + luhn_check_digit(payload)


def gen_card_tail0000():
    """末6位含0000的合法卡 → 模拟平台退回「账户已注销」"""
    payload = '622202' + ''.join(random.choices('0123456789', k=7)) \
        + '0000' + random.choice('0123456789')
    return payload + luhn_check_digit(payload)


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f'已生成 {path}（{len(rows)} 行）')


def build_chengguan_rows():
    rows = []
    # 12 行完全正常
    for _ in range(12):
        rows.append([gen_name(), gen_id_card(), gen_bank_card(),
                     f'{random.randint(5, 80) * 100}.00', '城关镇'])
    # 4 行格式合法，但会被财政平台退回
    rows.append([gen_name(), gen_id_card(), gen_card_tail0000(), '1500.00', '城关镇'])      # 账户已注销
    rows.append([gen_name(), gen_id_card(), gen_bank_card(), '60000.00', '城关镇'])          # 超单笔限额
    rows.append([gen_name(), gen_id_card(region='999000'), gen_bank_card(), '2000.00', '城关镇'])  # 信息不匹配
    rows.append(['钱异常', gen_id_card(), gen_bank_card(), '1800.00', '城关镇'])             # 户名不符
    # 9 行格式/重复校验失败
    bad_id = list(gen_id_card())
    bad_id[-1] = '1' if bad_id[-1] == '0' else '0'
    rows.append([gen_name(), ''.join(bad_id), gen_bank_card(), '1500.00', '城关镇'])         # 身份证校验位错
    bad_card = gen_bank_card()
    bad_card = bad_card[:-1] + str((int(bad_card[-1]) + 1) % 10)
    rows.append([gen_name(), gen_id_card(), bad_card, '1500.00', '城关镇'])                  # 银行卡校验错
    rows.append([gen_name(), gen_id_card(), gen_bank_card(), '-500.00', '城关镇'])           # 金额为负
    rows.append([gen_name(), gen_id_card(), gen_bank_card(), '100.555', '城关镇'])           # 三位小数
    rows.append([gen_name(), gen_id_card(), gen_bank_card(), 'abc', '城关镇'])               # 金额非数字
    rows.append([gen_name(), rows[0][1], gen_bank_card(), '1500.00', '城关镇'])              # 文件内重复
    rows.append([gen_name(), gen_id_card(), gen_bank_card(), '1500.00', '东城镇'])           # 乡镇不符
    rows.append([gen_name(), gen_id_card(), gen_bank_card(), '1500.00', ''])                 # 乡镇为空
    rows.append(['李', gen_id_card(), gen_bank_card(), '1500.00', '城关镇'])                 # 姓名过短
    return rows


def build_dongcheng_rows():
    return [[gen_name(), gen_id_card(), gen_bank_card(),
             f'{random.randint(6, 60) * 100}.00', '东城镇'] for _ in range(6)]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cg = build_chengguan_rows()
    dc = build_dongcheng_rows()
    write_csv(os.path.join(OUT_DIR, '城关镇_补贴名单_演示.csv'), cg)
    write_csv(os.path.join(OUT_DIR, '东城镇_补贴名单_演示.csv'), dc)

    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(HEADER)
        for r in cg:
            ws.append(r)
        xlsx_path = os.path.join(OUT_DIR, '城关镇_补贴名单_演示.xlsx')
        wb.save(xlsx_path)
        print(f'已生成 {xlsx_path}')
    except ImportError:
        print('（未安装 openpyxl，跳过 xlsx 示例）')

    print('\n城关镇演示文件预期结果：共 25 行 = 16 行校验通过（含 4 行平台退回）+ 9 行校验失败')


if __name__ == '__main__':
    main()
