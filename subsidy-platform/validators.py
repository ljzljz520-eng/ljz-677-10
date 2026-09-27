"""补贴名单数据校验：身份证号、银行卡号、金额、姓名"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

# 身份证校验位权重与校验码表（GB 11643-1999）
ID_CARD_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CARD_CHECK_CODES = '10X98765432'

MAX_AMOUNT = Decimal('999999.99')   # 单笔金额上限


def compute_id_check_code(first17: str) -> str:
    """根据身份证前17位计算校验码"""
    total = sum(int(d) * w for d, w in zip(first17, ID_CARD_WEIGHTS))
    return ID_CARD_CHECK_CODES[total % 11]


def validate_id_card(id_card: str):
    """校验18位身份证号：格式 + 出生日期 + 校验位"""
    id_card = (id_card or '').strip().upper()
    if not re.fullmatch(r'\d{17}[\dX]', id_card):
        return False, '身份证号须为18位（前17位数字，末位可为X）'
    try:
        date(int(id_card[6:10]), int(id_card[10:12]), int(id_card[12:14]))
    except ValueError:
        return False, '身份证号中的出生日期无效'
    if compute_id_check_code(id_card[:17]) != id_card[17]:
        return False, '身份证号校验位错误'
    return True, ''


def luhn_check_digit(payload: str) -> str:
    """计算银行卡 Luhn 校验位（payload 不含校验位）"""
    total = 0
    for i, ch in enumerate(reversed(payload)):
        n = int(ch)
        if i % 2 == 0:          # 加上校验位后，这些位处于偶数位置需加倍
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return str((10 - total % 10) % 10)


def validate_bank_card(card: str):
    """校验银行卡号：16-19位数字 + Luhn 算法"""
    card = (card or '').strip().replace(' ', '')
    if not re.fullmatch(r'\d{16,19}', card):
        return False, '银行卡号须为16-19位数字'
    total = 0
    for i, ch in enumerate(reversed(card)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    if total % 10 != 0:
        return False, '银行卡号校验失败（卡号有误）'
    return True, ''


def validate_amount(text: str):
    """校验金额：>0、最多两位小数、不超过上限。返回 (是否通过, 错误信息, Decimal值)"""
    text = (text or '').strip().replace(',', '')
    if not text:
        return False, '金额不能为空', None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return False, f'金额格式错误："{text}"', None
    if value <= 0:
        return False, '金额必须大于0', None
    if value > MAX_AMOUNT:
        return False, f'金额超过单笔上限 {MAX_AMOUNT} 元', None
    if -value.as_tuple().exponent > 2:
        return False, '金额最多保留两位小数', None
    return True, '', value


def validate_name(name: str):
    """校验姓名：2-30个汉字（允许间隔号·）"""
    name = (name or '').strip()
    if not name:
        return False, '姓名不能为空'
    if not re.fullmatch(r'[一-龥·]{2,30}', name):
        return False, '姓名须为2-30个汉字'
    return True, ''
