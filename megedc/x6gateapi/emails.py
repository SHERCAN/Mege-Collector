from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Template, Context


def send_alert(alert, rt_alarm):

    if not alert.emails:
        return

    load_tags = '{% load alert_emails %}'

    html_template = (
        Template(load_tags + alert.html_msg_template)
        if alert.html_msg_template is not None else
        None
    )
    msg_template = Template(load_tags + alert.msg_template)
    subject_template = Template(load_tags + alert.subject_template)
    context = Context({
        'alert': alert,
        'alarm': rt_alarm,
        'extra': {}
    })

    msg_data = msg_template.render(context)
    html_data = (
        html_template.render(context)
        if html_template is not None else
        None
    )
    subject_data = subject_template.render(context)
    from_email = None
    if alert.from_email is not None and alert.from_email_name:
        from_email = '"%s" <%s>' % (alert.from_email_name, alert.from_email)
    elif alert.from_email is None and alert.from_email_name:
        from_email = '"%s" <%s>' % (
            alert.from_email_name,
            settings.DEFAULT_FROM_EMAIL
        )
    elif alert.from_email and not alert.from_email_name:
        from_email = alert.from_email
    email = EmailMultiAlternatives(
        subject_data,
        msg_data,
        from_email,
        [],
        alert.emails,
    )
    if html_data is not None:
        email.attach_alternative(html_data, 'text/html')
    return email.send()
