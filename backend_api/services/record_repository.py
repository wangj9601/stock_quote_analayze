"""
推送记录数据访问层 (RecordRepository)
负责推送记录的数据库操作
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from backend_api.models import PushRecord


class RecordRepository:
    """推送记录数据访问层"""
    
    def __init__(self, db: Session):
        """
        初始化记录仓库
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    def create_record(
        self,
        user_id: int,
        push_date: date,
        push_time: str,
        report_type: str,
        channel_status: Dict[str, str],
        report_file_path: Optional[str] = None,
        max_retries: int = 3
    ) -> PushRecord:
        """
        创建推送记录
        
        Args:
            user_id: 用户ID
            push_date: 推送日期
            push_time: 推送时间 (如 "09:30")
            report_type: 报告类型 ('summary' 或 'detailed')
            channel_status: 渠道状态字典 (如 {"wechat": "pending", "email": "pending"})
            report_file_path: 报告文件路径
            max_retries: 最大重试次数
            
        Returns:
            PushRecord: 创建的推送记录
        """
        record = PushRecord(
            user_id=user_id,
            push_date=push_date,
            push_time=push_time,
            report_type=report_type,
            channel_status=channel_status,
            status="pending",
            report_file_path=report_file_path,
            error_messages={},
            retry_count=0,
            max_retries=max_retries,
            created_at=datetime.now()
        )
        
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        
        return record
    
    def update_record_status(
        self,
        record_id: int,
        status: str,
        channel_status: Optional[Dict[str, str]] = None,
        error_messages: Optional[Dict[str, str]] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        retry_count: Optional[int] = None
    ) -> Optional[PushRecord]:
        """
        更新推送记录状态
        
        Args:
            record_id: 记录ID
            status: 整体状态 ('pending', 'processing', 'success', 'partial_success', 'failed')
            channel_status: 渠道状态字典 (如 {"wechat": "success", "email": "failed"})
            error_messages: 错误信息字典 (如 {"wechat": null, "email": "SMTP error"})
            started_at: 开始时间
            completed_at: 完成时间
            retry_count: 重试次数
            
        Returns:
            Optional[PushRecord]: 更新后的推送记录，如果记录不存在则返回None
        """
        record = self.db.query(PushRecord).filter(PushRecord.id == record_id).first()
        
        if not record:
            return None
        
        # 更新状态
        record.status = status
        
        # 更新渠道状态
        if channel_status is not None:
            record.channel_status = channel_status
        
        # 更新错误信息
        if error_messages is not None:
            record.error_messages = error_messages
        
        # 更新时间戳
        if started_at is not None:
            record.started_at = started_at
        
        if completed_at is not None:
            record.completed_at = completed_at
        
        # 更新重试次数
        if retry_count is not None:
            record.retry_count = retry_count
        
        self.db.commit()
        self.db.refresh(record)
        
        return record
    
    def get_user_records(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = 0
    ) -> List[PushRecord]:
        """
        获取用户的推送记录（支持筛选）
        
        Args:
            user_id: 用户ID
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            status: 推送状态（可选）
            limit: 返回记录数量限制（可选）
            offset: 偏移量（可选）
            
        Returns:
            List[PushRecord]: 推送记录列表
        """
        query = self.db.query(PushRecord).filter(PushRecord.user_id == user_id)
        
        # 日期范围筛选
        if start_date is not None:
            query = query.filter(PushRecord.push_date >= start_date)
        
        if end_date is not None:
            query = query.filter(PushRecord.push_date <= end_date)
        
        # 状态筛选
        if status is not None:
            query = query.filter(PushRecord.status == status)
        
        # 按创建时间倒序排列
        query = query.order_by(PushRecord.created_at.desc())
        
        # 分页
        if offset:
            query = query.offset(offset)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_record_by_id(self, record_id: int) -> Optional[PushRecord]:
        """
        根据ID获取推送记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            Optional[PushRecord]: 推送记录，如果不存在则返回None
        """
        return self.db.query(PushRecord).filter(PushRecord.id == record_id).first()
    
    def get_failed_records(
        self,
        user_id: Optional[int] = None,
        max_retries_reached: bool = False
    ) -> List[PushRecord]:
        """
        获取失败的推送记录
        
        Args:
            user_id: 用户ID（可选，如果提供则只返回该用户的记录）
            max_retries_reached: 是否只返回已达到最大重试次数的记录
            
        Returns:
            List[PushRecord]: 失败的推送记录列表
        """
        query = self.db.query(PushRecord).filter(
            or_(
                PushRecord.status == "failed",
                PushRecord.status == "partial_success"
            )
        )
        
        if user_id is not None:
            query = query.filter(PushRecord.user_id == user_id)
        
        if max_retries_reached:
            query = query.filter(PushRecord.retry_count >= PushRecord.max_retries)
        else:
            query = query.filter(PushRecord.retry_count < PushRecord.max_retries)
        
        return query.all()
    
    def check_duplicate_push(
        self,
        user_id: int,
        push_date: date,
        push_time: str
    ) -> bool:
        """
        检查是否存在重复的推送记录
        
        Args:
            user_id: 用户ID
            push_date: 推送日期
            push_time: 推送时间
            
        Returns:
            bool: 如果存在成功或处理中的推送记录则返回True，否则返回False
        """
        existing_record = self.db.query(PushRecord).filter(
            and_(
                PushRecord.user_id == user_id,
                PushRecord.push_date == push_date,
                PushRecord.push_time == push_time,
                or_(
                    PushRecord.status == "success",
                    PushRecord.status == "processing",
                    PushRecord.status == "partial_success"
                )
            )
        ).first()
        
        return existing_record is not None
    
    def get_records_by_date_range(
        self,
        start_date: date,
        end_date: date,
        status: Optional[str] = None
    ) -> List[PushRecord]:
        """
        获取指定日期范围内的所有推送记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            status: 推送状态（可选）
            
        Returns:
            List[PushRecord]: 推送记录列表
        """
        query = self.db.query(PushRecord).filter(
            and_(
                PushRecord.push_date >= start_date,
                PushRecord.push_date <= end_date
            )
        )
        
        if status is not None:
            query = query.filter(PushRecord.status == status)
        
        return query.order_by(PushRecord.push_date.desc(), PushRecord.created_at.desc()).all()
    
    def count_user_records(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[str] = None
    ) -> int:
        """
        统计用户的推送记录数量
        
        Args:
            user_id: 用户ID
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            status: 推送状态（可选）
            
        Returns:
            int: 记录数量
        """
        query = self.db.query(PushRecord).filter(PushRecord.user_id == user_id)
        
        if start_date is not None:
            query = query.filter(PushRecord.push_date >= start_date)
        
        if end_date is not None:
            query = query.filter(PushRecord.push_date <= end_date)
        
        if status is not None:
            query = query.filter(PushRecord.status == status)
        
        return query.count()
    
    def delete_old_records(self, days: int = 90) -> int:
        """
        删除旧的推送记录
        
        Args:
            days: 保留最近多少天的记录，默认90天
            
        Returns:
            int: 删除的记录数量
        """
        from datetime import timedelta
        
        cutoff_date = date.today() - timedelta(days=days)
        
        deleted_count = self.db.query(PushRecord).filter(
            PushRecord.push_date < cutoff_date
        ).delete()
        
        self.db.commit()
        
        return deleted_count
