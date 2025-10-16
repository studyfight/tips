from typing import List, Dict, Any

from common.clients import InspectionSystemClient
from .schemas import TipsIn, TipsOut, TipsBatchIn, TipsBatchOut, PersonTipOut, PersonTipIn
import os, json

class PersonalizedTipsAgent:
	"""个性化体检前提示Agent：预约成功后输出提醒（列表）与预约结果结论。"""
	def __init__(self, client: InspectionSystemClient | None = None):
		self.client = client or InspectionSystemClient()
		# 外置规则（可选）：tips/config/rules.json
		self.rules: Dict[str, Any] = self._load_rules()

	def _load_rules(self) -> Dict[str, Any]:
		try:
			base_dir = os.path.dirname(__file__)
			rules_path = os.path.join(base_dir, "config", "rules.json")
			if os.path.exists(rules_path):
				with open(rules_path, "r", encoding="utf-8") as f:
					return json.load(f)
		except Exception:
			pass
		# 默认内置规则（v2 schema：通用模板+规则列表），可被外置文件覆盖
		return {
			"schema": "v2",
			"version": "default",
			"common": {
				"templates": [
					"体检周一至周六上午进行，建议{time_window}到检；周日及法定假日停检。",
					"地点：医院西侧综合楼一楼健康管理中心；从西南门进入，车辆停放西侧停车场。",
					"携带身份证/有效证件，按导引完成检查（70岁以上建议家属陪同）。",
					"前三天避免饮酒/熬夜/剧烈运动，清淡饮食，保证睡眠。",
					"前一晚20:00后禁食；当天空腹抽血，饮水不超过300ml，空腹项目后再进食。",
					"着装宽松，避免紧身/连衣裙/连裤袜/亮片；不佩戴饰品。",
					"尽量当日完成所有项目（预约项目除外），并交回导检单；报告预计7个工作日。"
				]
			},
			"rules": [
				{"id": "female_menstruation", "when": {"gender": ["female"]}, "messages": ["女性尽量避开月经期进行血尿/妇检。"]},
				{"id": "female_unmarried", "when": {"gender": ["female"], "marital_status": ["未婚"]}, "messages": ["妇科检查限已婚（有性生活史），未婚者可不做该项或改期。"]},
				{"id": "pregnancy_xray", "when": {"is_pregnant": true}, "messages": ["孕期勿做X线相关检查（DR/CT/钼靶/双能X线），需检查请先告知医务人员。"]},
				{"id": "chronic_htn_chd", "when": {"chronic_contains_any": ["高血压","冠心病"]}, "messages": ["高血压/冠心病：当晨可少量饮水(<20ml)按时服药。"]},
				{"id": "chronic_dm", "when": {"chronic_contains_any": ["糖尿病"]}, "messages": ["糖尿病：随身带药，空腹项目后尽快进食并按医嘱用药，避免低血糖。"]},
				{"id": "items_urology_us", "when": {"items_contains_any": ["前列腺","膀胱","子宫附件","盆腔"]}, "messages": ["前列腺/膀胱/子宫附件彩超前2~3小时尽量不解小便，保持膀胱充盈。"]},
				{"id": "items_urine", "when": {"items_contains_any": ["尿常规","尿检"]}, "messages": ["尿检：采集中段尿8~10ml，女性避开月经期。"]},
				{"id": "items_stool", "when": {"items_contains_any": ["粪便","便潜血"]}, "messages": ["粪便：取蚕豆大小，勿与尿液混合；有黏液/脓血取异常部位送检。"]},
				{"id": "items_endoscopy", "when": {"items_contains_any": ["胃镜","肠镜","胃肠镜"]}, "messages": ["胃/肠镜：前一晚禁食，当日空腹；无痛镜需有人陪同，当日不驾车。"]},
				{"id": "items_xray", "when": {"items_contains_any": ["DR","X线","CT","钼靶","双能X线"]}, "messages": ["X线检查有电离辐射，孕期女性勿做；检查时去除金属物。"]},
				{"id": "items_mri", "when": {"items_contains_any": ["磁共振","MRI","MR"]}, "messages": ["磁共振：体内金属植入/支架/起搏器者先咨询专科医师确认可检。"]}
			]
		}

	def run(self, payload: TipsIn) -> TipsOut:
		# 进入此方法前，TipsIn 已校验 appointment_result.status == "success"
		lines: List[str] = [
			"体检前8小时避免进食，清淡饮食。",
			"体检当日早晨不饮茶咖啡，空腹抽血。",
			"请携带身份证件，提前15分钟到达体检中心。",
		]
		result_text = "预约成功，请按时到检。"
		return TipsOut(reminder=lines, appointment_result_message=result_text) 

	# ===== 批量个性化提示（用于第二天到检名单） =====
	def _season_time_window(self, date_str: str | None) -> str:
		try:
			from datetime import datetime
			dt = datetime.now() if not date_str else datetime.strptime(date_str, "%Y-%m-%d")
			md = int(dt.strftime("%m%d"))
			return "7:00~09:30" if 401 <= md <= 1031 else "7:30~09:30"
		except Exception:
			return "7:00~09:30"

	def _contains_any(self, text: str, kws: List[str]) -> bool:
		return any(k for k in kws if k and k in text)

	def _gen_person_messages(self, p: PersonTipIn) -> List[str]:
		# 若为 v2 规则：使用通用模板 + 规则匹配
		if isinstance(self.rules, dict) and isinstance(self.rules.get("rules"), list):
			msgs: List[str] = []
			time_window = self._season_time_window(p.appointment_date)
			for tpl in (self.rules.get("common", {}) or {}).get("templates", []) or []:
				try:
					msgs.append(str(tpl).format(time_window=time_window))
				except Exception:
					msgs.append(str(tpl))
			# 规则匹配
			def _contains_any_kw(arr: List[str] | None, kws: List[str]) -> bool:
				text = " ".join(arr or [])
				return self._contains_any(text, kws)
			for rule in self.rules.get("rules", []) or []:
				when = rule.get("when", {}) or {}
				ok = True
				gender = (p.gender or "").lower()
				if when.get("gender") and gender not in [str(x).lower() for x in when.get("gender")]:
					ok = False
				if ok and when.get("marital_status") and (p.marital_status or "") not in when.get("marital_status"):
					ok = False
				if ok and ("is_pregnant" in when) and bool(p.is_pregnant) != bool(when.get("is_pregnant")):
					ok = False
				if ok and when.get("min_age") is not None and (p.age or 0) < int(when.get("min_age")):
					ok = False
				if ok and when.get("max_age") is not None and (p.age or 0) > int(when.get("max_age")):
					ok = False
				if ok and when.get("chronic_contains_any") and not _contains_any_kw(p.chronic_conditions, [str(x) for x in when.get("chronic_contains_any")]):
					ok = False
				if ok and when.get("items_contains_any") and not _contains_any_kw(p.check_items, [str(x) for x in when.get("items_contains_any")]):
					ok = False
				if not ok:
					continue
				for m in rule.get("messages", []) or []:
					msgs.append(str(m))
			return msgs
		# 兼容旧版规则：沿用内置逻辑
		msgs: List[str] = []
		# 通用要点（基于医院注意事项）
		time_window = self._season_time_window(p.appointment_date)
		msgs.append(self.rules["common"]["time"].format(time_window=time_window))
		msgs.append(self.rules["common"]["place"]) 
		msgs.append(self.rules["common"]["id"]) 
		msgs.append(self.rules["common"]["lifestyle"]) 
		msgs.append(self.rules["common"]["fasting"]) 
		msgs.append(self.rules["common"]["clothes"]) 
		# 性别/妊娠
		gender = (p.gender or "").lower()
		if gender == "female":
			msgs.append(self.rules["female"]["menstruation"]) 
			if p.marital_status == "未婚":
				msgs.append(self.rules["female"]["marital"]) 
		if p.is_pregnant:
			msgs.append(self.rules["pregnancy"]) 
		# 慢病与用药
		chronic = " ".join(p.chronic_conditions or [])
		if self._contains_any(chronic, ["高血压", "冠心病"]):
			msgs.append(self.rules["chronic"]["htn_chd"]) 
		if self._contains_any(chronic, ["糖尿病"]):
			msgs.append(self.rules["chronic"]["dm"]) 
		# 预约项目专项
		items = " ".join(p.check_items or [])
		if self._contains_any(items, ["前列腺", "膀胱", "子宫附件", "盆腔"]):
			msgs.append(self.rules["items"]["urology_us"]) 
		if self._contains_any(items, ["尿常规", "尿检"]):
			msgs.append(self.rules["items"]["urine"]) 
		if self._contains_any(items, ["粪便", "便潜血"]):
			msgs.append(self.rules["items"]["stool"]) 
		if self._contains_any(items, ["胃镜", "肠镜", "胃肠镜"]):
			msgs.append(self.rules["items"]["endoscopy"]) 
		if self._contains_any(items, ["DR", "X线", "CT", "钼靶", "双能X线"]):
			msgs.append(self.rules["items"]["xray"]) 
		if self._contains_any(items, ["磁共振", "MRI", "MR"]):
			msgs.append(self.rules["items"]["mri"]) 
		# 当日完成/回收导检单/出报告
		msgs.append(self.rules["common"]["finish"]) 
		return msgs

	def run_batch(self, payload: TipsBatchIn) -> TipsBatchOut:
		import uuid
		from datetime import datetime
		reminders: List[PersonTipOut] = []
		for person in payload.persons:
			msgs = self._gen_person_messages(person)
			reminders.append(PersonTipOut(name=person.name, phone=person.phone, messages=msgs, text="\n".join(f"- {m}" for m in msgs)))
		return TipsBatchOut(
			trace_id=f"req_{uuid.uuid4().hex[:12]}",
			status="success",
			timestamp=datetime.now().isoformat(),
			data={"user_id": payload.user_id, "reminders": [r.model_dump() for r in reminders]}
		)