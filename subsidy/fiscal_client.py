"""模拟财政平台客户端。

真实部署时，将 submit_batch 替换为对财政平台接口的 HTTP 调用（加签、报文加密等）。
这里用确定性的业务规则模拟平台返回结果，便于演示与自动化测试：
  - 银行卡号以 00 结尾   -> 账户已销户
  - 银行卡号以 99 结尾   -> 账户冻结
  - 金额超过 20000 元    -> 超平台单笔限额
  - 姓名含“测”字         -> 户名与账户不符
  - 其余                 -> 受理成功
"""

PLATFORM_LIMIT_CENTS = 20000_00  # 财政平台单笔限额 2 万元


class FiscalPlatformError(Exception):
    """平台通讯异常（整批失败）。"""


def submit_batch(batch_no, records):
    """上送一批记录，返回逐条结果：[{row_no, success, message}]"""
    results = []
    for r in records:
        err = _platform_check(r)
        results.append({
            "row_no": r["row_no"],
            "success": err is None,
            "message": err if err else "受理成功",
        })
    return results


def _platform_check(r):
    card = r["bank_card"]
    if card.endswith("00"):
        return "银行反馈：账户已销户"
    if card.endswith("99"):
        return "银行反馈：账户状态异常（已冻结）"
    if r["amount_cents"] > PLATFORM_LIMIT_CENTS:
        return "超过财政平台单笔限额20000.00元，退回修改"
    if "测" in r["name"]:
        return "户名与银行卡户名不符"
    return None
