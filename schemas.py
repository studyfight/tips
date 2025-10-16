from typing import Optional
from pydantic import BaseModel, Field
from pydantic import ConfigDict, field_validator
from common.clients import AppointmentResult

class TipsIn(BaseModel):
	"""个性化提示输入：仅在预约成功后触发。"""
	user_id: str
	appointment_result: AppointmentResult  # 必须是成功的预约结果

	@field_validator("appointment_result")
	@classmethod
	def _must_success(cls, v: AppointmentResult):
		if v.status != "success":
			raise ValueError("TipsIn 仅在预约成功后使用（status 必须为 'success'）")
		return v

class TipsOut(BaseModel):
	"""个性化提示输出：标准JSON结构（使用中文别名键）。"""
	# 允许用字段名传入（reminder/appointment_result_message），序列化时再使用别名
	model_config = ConfigDict(populate_by_name=True)
	reminder: list[str] = Field(alias="提醒")  # 多条提醒，按行返回
	appointment_result_message: str = Field(alias="预约结果")  # 去掉“预约结果：”前缀，直接给结论文案 

# ===== 批量个性化提示（独立于 recom2） =====
class PersonTipIn(BaseModel):
	name: str
	phone: str | None = None
	age: int | None = None
	gender: str | None = None  # male/female
	appointment_date: str | None = None  # YYYY-MM-DD
	appointment_time: str | None = None  # HH:MM
	department: str | None = None
	check_items: list[str] | None = None
	chronic_conditions: list[str] | None = None
	is_pregnant: bool | None = None
	marital_status: str | None = None  # 已婚/未婚

class TipsBatchIn(BaseModel):
	user_id: str
	persons: list[PersonTipIn]

class PersonTipOut(BaseModel):
	name: str
	phone: str | None = None
	messages: list[str]
	text: str

class TipsBatchOut(BaseModel):
	trace_id: str
	status: str
	timestamp: str
	data: dict  # { user_id, reminders: List[PersonTipOut] }