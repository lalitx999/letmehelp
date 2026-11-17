from celery import shared_task

from .services import report_service


@shared_task
def generate_report_task(export_id: int):
    report_service.build_report(export_id)
