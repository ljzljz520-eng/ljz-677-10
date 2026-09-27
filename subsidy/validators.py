"""补贴名单字段校验规则：身份证、银行卡、金额、姓名。"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

# 身份证加权因子与校验码表（GB 11643-1999）
ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CHECK_CODES = "10X98765432"

MAX_AMOUNT_CENTS = 50000_00  # 系统单笔上限 5 万元


def check_id_card(id_card):
    """校验身份证号，返回错误信息；通过返回 None。"""
    id_card = (id_card or "").strip().upper()
    if not re.fullmatch(r"\d{17}[\dX]", id_card):
        return "身份证号须为18位（末位可为X）"
    try:
        year, month, day = int(id_card[6:10]), int(id_card[10:12]), int(id_card[12:14])
        birth = date(year, month, day)
    except ValueError:
        return "身份证出生日期无效"
    if birth > date.today():
        return "身份证出生日期晚于当前日期"
    if year < 1900:
        return "身份证出生年份不合理"
    total = sum(int(id_card[i]) * ID_WEIGHTS[i] for i in range(17))
    if ID_CHECK_CODES[total % 11] != id_card[17]:
        return "身份证校验码不正确"
    return None


def check_bank_card(card):
    """Luhn 算法校验银行卡号，返回错误信息；通过返回 None。"""
    card = (card or "").strip().replace(" ", "")
    if not re.fullmatch(r"\d{13,19}", card):
        return "银行卡号须为13-19位数字"
    total = 0
    for i, ch in enumerate(reversed(card)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    if total % 10 != 0:
        return "银行卡号校验失败（卡号有误）"
    return None


def parse_amount(text):
    """解析金额，返回 (金额分, 错误信息)。"""
    text = (text or "").strip().replace(",", "").replace("￥", "").replace("元", "")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", text):
        return None, "金额须为不小于0的数字，最多两位小数"
    try:
        cents = int((Decimal(text) * 100).to_integral_value())
    except InvalidOperation:
        return None, "金额格式错误"
    if cents <= 0:
        return None, "金额必须大于0"
    if cents > MAX_AMOUNT_CENTS:
        return None, "单笔金额不能超过50000.00元"
    return cents, None


def check_name(name):
    """校验补贴对象姓名。"""
    name = (name or "").strip()
    if not name:
        return "补贴对象姓名不能为空"
    if len(name) > 30:
        return "姓名长度超过30字"
    if not re.fullmatch(r"[一-龥·•A-Za-z]+", name):
        return "姓名含非法字符"
    return None
