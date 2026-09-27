#!/usr/bin/env python3
"""单元测试：校验规则、导入流程、分批上送、乡镇数据隔离。"""
import os
import sys
import tempfile

# 在导入 subsidy 模块前指定独立测试数据库
_tmp = tempfile.mkdtemp()
os.environ["SUBSIDY_DB"] = os.path.join(_tmp, "test.db")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from subsidy import db, services
from subsidy.validators import check_id_card, check_bank_card, parse_amount, check_name


def make_csv(rows, header="补贴对象,身份证号,银行卡号,金额,乡镇"):
    lines = [header] + [",".join(r) for r in rows]
    return "\n".join(lines).encode("utf-8-sig")


# 一组通过校验的测试数据（与 gen_sample 同算法）
from subsidy.validators import ID_WEIGHTS, ID_CHECK_CODES

def make_id(seq):
    base = "3413221990010%04d" % seq
    total = sum(int(base[i]) * ID_WEIGHTS[i] for i in range(17))
    return base + ID_CHECK_CODES[total % 11]

def make_card(suffix=""):
    """生成通过 Luhn 的 16 位卡号；suffix 指定完整卡号的结尾（循环至校验位匹配）。"""
    import random
    rng = random.Random(42)
    while True:
        n_mid = 15 - 6 - (len(suffix) - 1 if suffix else 0)
        body = "622202" + "".join(rng.choice("0123456789") for _ in range(n_mid))
        if suffix:
            body += suffix[:-1]
        total = 0
        for i, ch in enumerate(reversed(body + "0")):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        check = str((10 - total % 10) % 10)
        if not suffix or check == suffix[-1]:
            return body + check


class TestValidators(unittest.TestCase):
    def test_id_card_ok(self):
        self.assertIsNone(check_id_card(make_id(1111)))

    def test_id_card_bad_checksum(self):
        good = make_id(1111)
        bad = good[:-1] + ("0" if good[-1] != "0" else "1")
        self.assertEqual(check_id_card(bad), "身份证校验码不正确")

    def test_id_card_bad_format(self):
        self.assertIsNotNone(check_id_card("12345"))
        self.assertIsNotNone(check_id_card(""))

    def test_id_card_bad_date(self):
        base = "34132219991301111"  # 13月
        total = sum(int(base[i]) * ID_WEIGHTS[i] for i in range(17))
        card = base + ID_CHECK_CODES[total % 11]
        self.assertEqual(check_id_card(card), "身份证出生日期无效")

    def test_bank_card(self):
        self.assertIsNone(check_bank_card(make_card()))
        self.assertIsNotNone(check_bank_card("6222020011112222"))  # Luhn 错
        self.assertIsNotNone(check_bank_card("123"))               # 太短
        self.assertIsNotNone(check_bank_card("abcd1234567890123")) # 非数字

    def test_amount(self):
        self.assertEqual(parse_amount("100")[0], 10000)
        self.assertEqual(parse_amount("0.01")[0], 1)
        self.assertEqual(parse_amount("1,234.56")[0], 123456)
        self.assertIsNotNone(parse_amount("10.123")[1])   # 三位小数
        self.assertIsNotNone(parse_amount("-5")[1])       # 负数
        self.assertIsNotNone(parse_amount("0")[1])        # 零
        self.assertIsNotNone(parse_amount("99999")[1])    # 超上限
        self.assertIsNotNone(parse_amount("abc")[1])

    def test_name(self):
        self.assertIsNone(check_name("张三"))
        self.assertIsNotNone(check_name(""))
        self.assertIsNotNone(check_name("张三123"))


class TestFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.user_cd = db.verify_user("chengdong", "Town@2026")
        cls.user_cx = db.verify_user("chengxi", "Town@2026")
        cls.admin = db.verify_user("admin", "Admin@2026")
        assert cls.user_cd and cls.user_cx and cls.admin

    def test_01_import_and_validate(self):
        rows = [
            ("张三", make_id(2001), make_card(), "100.00", "城东镇"),   # OK
            ("李四", make_id(2002), make_card(), "200.00", "城东镇"),   # OK
            ("王五", make_id(2002), make_card(), "300.00", "城东镇"),   # 文件内重复
            ("赵六", make_id(2003), make_card(), "10.123", "城东镇"),   # 金额错
            ("孙七", make_id(2004), make_card(), "500.00", "城西镇"),   # 乡镇不符
        ]
        task_id, s = services.import_file(self.user_cd, "t1.csv", make_csv(rows))
        self.assertEqual((s["total"], s["valid"], s["invalid"]), (5, 2, 3))
        TestFlow.task_cd = task_id

    def test_02_duplicate_across_tasks(self):
        # 与 test_01 中已导入的身份证重复
        rows = [("新人", make_id(2001), make_card(), "100.00", "城东镇")]
        task_id, s = services.import_file(self.user_cd, "t2.csv", make_csv(rows))
        self.assertEqual(s["valid"], 0)
        _, records = services.list_records(self.user_cd, task_id)
        self.assertIn("历史任务", records[0]["check_message"])

    def test_03_submit_batches(self):
        # 造 25 条合法记录 -> 应分 2 批（20+5），其中 1 条尾号 00 被平台退回
        rows = []
        cn = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥春夏秋冬"
        for i in range(24):
            rows.append(("村民" + cn[i], make_id(3000 + i), make_card(), "100.00", "城东镇"))
        rows.append(("销户户", make_id(3100), make_card("00"), "100.00", "城东镇"))
        task_id, s = services.import_file(self.user_cd, "t3.csv", make_csv(rows))
        self.assertEqual(s["valid"], 25)
        result = services.submit_task(self.user_cd, task_id)
        self.assertEqual(result["batches"], 2)
        self.assertEqual(result["success"], 24)
        self.assertEqual(result["failed"], 1)
        # 错误清单
        task, errors = services.list_errors(self.user_cd, task_id)
        self.assertEqual(len(errors), 1)
        self.assertIn("销户", errors[0]["submit_message"])
        # 重复上送应无待上送记录
        again = services.submit_task(self.user_cd, task_id)
        self.assertEqual(again["batches"], 0)

    def test_04_failed_record_can_reimport(self):
        # 平台退回的记录（销户户）不计入重复，可修正后重新导入
        rows = [("销户户", make_id(3100), make_card(), "100.00", "城东镇")]
        _, s = services.import_file(self.user_cd, "t4.csv", make_csv(rows))
        self.assertEqual(s["valid"], 1)

    def test_05_township_isolation(self):
        # 城西镇看不到城东镇的任务
        self.assertIsNone(services.get_task_for_user(self.user_cx, self.task_cd))
        # 城西镇任务列表为空（未导入过）
        self.assertEqual(services.list_tasks(self.user_cx), [])
        # 城东镇任务列表非空
        self.assertGreater(len(services.list_tasks(self.user_cd)), 0)
        # 管理员可见全部
        self.assertIsNotNone(services.get_task_for_user(self.admin, self.task_cd))
        # 城西镇提交城东镇任务 -> 无权限
        self.assertIsNone(services.submit_task(self.user_cx, self.task_cd))
        # 城西镇查城东镇错误清单 -> 无权限
        task, errors = services.list_errors(self.user_cx, self.task_cd)
        self.assertIsNone(task)

    def test_06_bad_file(self):
        with self.assertRaises(services.ImportError_):
            services.import_file(self.user_cd, "bad.csv", "不是表头\n1,2,3".encode("utf-8"))
        with self.assertRaises(services.ImportError_):
            services.import_file(self.user_cd, "empty.csv", "补贴对象,身份证号,银行卡号,金额,乡镇\n".encode("utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
