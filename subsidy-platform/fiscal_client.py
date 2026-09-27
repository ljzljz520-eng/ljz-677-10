"""模拟财政一体化平台接口。

真实环境中此处替换为财政平台的 HTTP/webservice 调用，
接口契约保持一致：按批次上送，逐笔返回受理结果。
"""


class FiscalPlatformError(Exception):
    """平台通讯异常"""


class MockFiscalPlatform:
    """模拟财政平台批量发放接口。

    演示用的确定性退回规则（命中即退回该笔）：
      1. 银行卡号末6位含 "0000"   → 账户已注销
      2. 单笔金额超过 50000 元     → 超过单笔发放限额
      3. 身份证号以 "999" 开头     → 身份证信息与姓名不匹配
      4. 姓名含 "异常" 二字        → 收款人姓名与银行账户户名不符
    """

    MAX_SINGLE_AMOUNT = 50000

    def submit_batch(self, batch_no: int, records: list) -> list:
        """上送一批记录，返回逐笔结果。

        records: [{'row_number', 'name', 'id_card', 'bank_card', 'amount'}, ...]
        return:  [{'row_number', 'success', 'message'}, ...]
        """
        results = []
        for rec in records:
            error = self._check(rec)
            results.append({
                'row_number': rec['row_number'],
                'success': error is None,
                'message': error or '发放成功',
            })
        return results

    def _check(self, rec):
        if '0000' in rec['bank_card'][-6:]:
            return '银行卡状态异常：账户已注销'
        if float(rec['amount']) > self.MAX_SINGLE_AMOUNT:
            return '超过单笔发放限额（50000.00元）'
        if rec['id_card'].startswith('999'):
            return '身份证信息与姓名不匹配'
        if '异常' in rec['name']:
            return '收款人姓名与银行账户户名不符'
        return None
