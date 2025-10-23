# -*- coding: utf-8 -*-
"""
tips/agent.py - 个性化体检提示智能代理

核心功能：
1. 批量生成个性化体检前注意事项
2. 基于规则引擎：根据性别、年龄、慢病、检查项目等匹配规则
3. 配置驱动：规则可通过JSON文件配置

并发安全：
- 无可变实例状态：self.rules和self.client初始化后不变
- 方法无副作用：run_batch仅根据输入生成输出
- 线程安全：多个并发请求可共用同一实例
"""

from typing import List, Dict, Any

from common.clients import InspectionSystemClient
from .schemas import TipsIn, TipsOut, TipsBatchIn, TipsBatchOut, PersonTipOut, PersonTipIn
import os, json

class PersonalizedTipsAgent:
	"""个性化体检前提示Agent
	
	设计原则：
	1. 规则驱动：通过JSON配置规则，不需训练模型
	2. 无状态设计：所有方法为纯函数，无副作用
	3. 配置灵活：支持v1/v2规则格式，向后兼容
	
	并发安全：
	- self.rules: 只读规则字典，初始化后不变
	- self.client: 只读客户端实例
	- 无全局可变状态，支持并发调用
	"""
	def __init__(self, client: InspectionSystemClient | None = None):
		"""初始化提示Agent
		
		Args:
			client: 体检系统客户端（预留，当前未使用）
		"""
		self.client = client or InspectionSystemClient()
		# 加载外部规则文件（可选）：tips/config/rules.json
		# 如果文件不存在，使用内置默认规则
		self.rules: Dict[str, Any] = self._load_rules()

	def _load_rules(self) -> Dict[str, Any]:
		"""加载提示规则配置
		
		加载顺序：
		1. 尝试从 tips/config/rules.json 加载外部配置
		2. 如果失败，使用下方内置默认规则
		
		规则格式（v2 schema）：
		- common.templates: 通用模板文案
		- rules: 条件匹配规则列表
			- id: 规则标识
			- when: 触发条件（gender/age/chronic_conditions/items等）
			- messages: 命中后添加的提示内容
		
		Returns:
			规则配置字典
		"""
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
		"""为单个人员生成个性化提示消息
		
		处理逻辑：
		1. 添加通用模板文案（时间、地点、禁食等）
		2. 逐条匹配个性化规则：
		   - 性别相关：女性注意事项、孕期禁忌
		   - 年龄相关：70岁以上家属陪同
		   - 慢病相关：糖尿病、高血压用药指导
		   - 检查项目相关：胃镜、彩超、X线等专项准备
		3. 返回排序后的消息列表
		
		并发安全：
		- 纯函数，不修改实例状态
		- 仅读取self.rules，不修改
		- 多线程并发调用安全
		
		Args:
			p: 单个人员的信息
			
		Returns:
			个性化提示消息列表
		"""
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
		"""批量生成个性化提示主方法
		
		处理流程：
		1. 遍历每个人员信息
		2. 为每个人生成个性化消息
		3. 组装返回结果，包含trace_id和timestamp
		
		并发安全：
		- 纯函数，无副作用
		- 不修改实例状态
		- 多个并发请求互不影响
		
		用户区分：
		- payload.user_id: 业务层面的用户标识
		- trace_id: 系统生成的请求追踪ID
		- timestamp: 响应时间戳
		
		Args:
			payload: 批量请求输入，包含user_id和persons列表
			
		Returns:
			批量提示结果，包含每个人的提示内容
		"""
		import uuid
		from datetime import datetime
		
		# 批量处理每个人员
		reminders: List[PersonTipOut] = []
		for person in payload.persons:
			# 为每个人生成个性化消息
			msgs = self._gen_person_messages(person)
			# 组装输出结果
			reminders.append(PersonTipOut(
				name=person.name, 
				phone=person.phone, 
				messages=msgs,  # 消息列表
				text="\n".join(f"- {m}" for m in msgs)  # 格式化文本
			))
		
		# 返回标准化响应
		return TipsBatchOut(
			trace_id=f"req_{uuid.uuid4().hex[:12]}",  # 生成请求追踪ID
			status="success",
			timestamp=datetime.now().isoformat(),  # ISO 8601时间戳
			data={
				"user_id": payload.user_id,  # 返回用户ID
				"reminders": [r.model_dump() for r in reminders]  # 批量提示结果
			}
		)