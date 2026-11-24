from django.urls import path

from .views import catalog, money, people, system, tools

app_name = "dashboard"

urlpatterns = [
    path("", system.overview, name="overview"),

    # การสอน: หมวด
    path("categories/", catalog.category_list, name="category_list"),
    path("categories/new/", catalog.category_form, name="category_add"),
    path("categories/<int:category_id>/edit/", catalog.category_form, name="category_edit"),
    path("categories/<int:category_id>/toggle/", catalog.category_toggle, name="category_toggle"),
    path("categories/<int:category_id>/delete/", catalog.category_delete, name="category_delete"),

    # การสอน: คอร์ส
    path("courses/", catalog.course_list, name="course_list"),
    path("courses/new/", catalog.course_form, name="course_add"),
    path("courses/bulk/", catalog.course_bulk, name="course_bulk"),
    path("courses/<int:course_id>/edit/", catalog.course_form, name="course_edit"),
    path("courses/<int:course_id>/toggle/<str:field>/", catalog.course_toggle, name="course_toggle"),
    path("courses/<int:course_id>/duplicate/", catalog.course_duplicate, name="course_duplicate"),
    path("courses/<int:course_id>/delete/", catalog.course_delete, name="course_delete"),
    path("courses/<int:course_id>/content/", catalog.course_content, name="course_content"),

    # บท / คลิป / ไฟล์แนบ / แพ็กเกจ
    path("courses/<int:course_id>/sections/new/", catalog.section_form, name="section_add"),
    path("sections/<int:section_id>/edit/", catalog.section_form, name="section_edit"),
    path("sections/<int:section_id>/move/<str:direction>/", catalog.section_move, name="section_move"),
    path("sections/<int:section_id>/delete/", catalog.section_delete, name="section_delete"),
    path("courses/<int:course_id>/reorder/", catalog.course_reorder, name="course_reorder"),
    path("sections/<int:section_id>/sort/", catalog.section_sort, name="section_sort"),
    path("sections/<int:section_id>/lessons/new/", catalog.lesson_form, name="lesson_add"),
    path("lessons/<int:lesson_id>/edit/", catalog.lesson_form, name="lesson_edit"),
    path("lessons/<int:lesson_id>/move/<str:direction>/", catalog.lesson_move, name="lesson_move"),
    path("lessons/<int:lesson_id>/duplicate/", catalog.lesson_duplicate, name="lesson_duplicate"),
    path("lessons/<int:lesson_id>/delete/", catalog.lesson_delete, name="lesson_delete"),
    path("lessons/<int:lesson_id>/attachments/new/", catalog.attachment_form, name="attachment_add"),
    path("attachments/<int:attachment_id>/delete/", catalog.attachment_delete, name="attachment_delete"),
    path("courses/<int:course_id>/packages/new/", catalog.package_form, name="package_add"),
    path("packages/<int:package_id>/edit/", catalog.package_form, name="package_edit"),
    path("packages/<int:package_id>/toggle/", catalog.package_toggle, name="package_toggle"),
    path("packages/<int:package_id>/delete/", catalog.package_delete, name="package_delete"),

    # ผู้ใช้: นักเรียน
    path("students/", people.student_list, name="student_list"),
    path("students/new/", people.student_form, name="student_add"),
    path("students/import/", tools.student_import, name="student_import"),
    path("students/import/template.csv", tools.student_import_template, name="student_import_template"),
    path("broadcast/", tools.broadcast, name="broadcast"),
    path("students/<int:user_id>/", people.student_detail, name="student_detail"),
    path("students/<int:user_id>/edit/", people.student_form, name="student_edit"),
    path("students/<int:user_id>/manage/", people.student_manage, name="student_manage"),
    path("students/<int:user_id>/toggle/", people.student_toggle, name="student_toggle"),
    path("users/<int:user_id>/password/", people.student_password, name="user_password"),

    # ผู้ใช้: สิทธิ์เรียน
    path("enrollments/", people.enrollment_list, name="enrollment_list"),
    path("enrollments/grant/", people.enrollment_grant, name="enrollment_grant"),
    path("enrollments/bulk/", people.enrollment_bulk, name="enrollment_bulk"),
    path("enrollments/<int:enrollment_id>/extend/", people.enrollment_extend, name="enrollment_extend"),
    path("enrollments/<int:enrollment_id>/revoke/", people.enrollment_revoke, name="enrollment_revoke"),
    path("enrollments/<int:enrollment_id>/restore/", people.enrollment_restore, name="enrollment_restore"),
    path("enrollments/<int:enrollment_id>/remind/", people.enrollment_remind, name="enrollment_remind"),

    # การเงิน
    path("orders/", money.order_list, name="order_list"),
    path("orders/new/", money.order_form, name="order_add"),
    path("orders/<int:order_id>/", money.order_detail, name="order_detail"),
    path("orders/<int:order_id>/paid/", money.order_mark_paid, name="order_mark_paid"),
    path("orders/<int:order_id>/cancel/", money.order_cancel, name="order_cancel"),
    path("orders/<int:order_id>/refund/", money.order_refund, name="order_refund"),
    path("orders/<int:order_id>/resend/", money.order_resend, name="order_resend"),
    path("slips/", money.slip_list, name="slip_list"),
    path("slips/<int:slip_id>/view/", money.slip_view, name="slip_view"),
    path("slips/<int:slip_id>/decide/", money.slip_decide, name="slip_decide"),
    path("exports/", system.exports, name="exports"),
    path("exports/status/", system.export_status, name="export_status"),
    path("exports/<int:export_id>/download/", system.export_download, name="export_download"),

    # ระบบ
    path("admins/", system.admin_list, name="admin_list"),
    path("admins/new/", system.admin_form, name="admin_add"),
    path("admins/<int:user_id>/edit/", system.admin_form, name="admin_edit"),
    path("admins/<int:user_id>/toggle/", system.admin_toggle, name="admin_toggle"),
    path("settings/", system.site_settings, name="site_settings"),
    path("audit/", system.audit_list, name="audit_list"),
    path("trash/", system.trash_list, name="trash"),
    path("trash/<str:kind>/<int:obj_id>/restore/", system.trash_restore, name="trash_restore"),
    path("trash/<str:kind>/<int:obj_id>/purge/", system.trash_purge, name="trash_purge"),
]
