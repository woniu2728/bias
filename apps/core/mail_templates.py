from textwrap import dedent


DEFAULT_VERIFICATION_SUBJECT = "验证您的邮箱 - {{ site_name }}"
DEFAULT_VERIFICATION_TEXT = dedent(
    """
    您好 {{ username }}，

    感谢您注册 {{ site_name }}！

    请点击以下链接验证您的邮箱：
    {{ verification_url }}

    如果您没有注册 {{ site_name }} 账号，请忽略此邮件。

    此链接将在24小时后失效。

    ---
    {{ site_name }} 团队
    """
).strip()
DEFAULT_VERIFICATION_HTML = dedent(
    """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #3498db; color: white; padding: 20px; text-align: center; }
            .content { padding: 20px; background: #f9f9f9; }
            .button { display: inline-block; padding: 12px 24px; background: #3498db; color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }
            .footer { padding: 20px; text-align: center; color: #666; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{{ site_name }}</h1>
            </div>
            <div class="content">
                <h2>您好 {{ username }}，</h2>
                <p>感谢您注册 {{ site_name }}！</p>
                <p>请点击下方按钮验证您的邮箱：</p>
                <a href="{{ verification_url }}" class="button">验证邮箱</a>
                <p>或复制以下链接到浏览器：</p>
                <p style="word-break: break-all; color: #666;">{{ verification_url }}</p>
                <p>如果您没有注册 {{ site_name }} 账号，请忽略此邮件。</p>
                <p style="color: #999; font-size: 14px;">此链接将在24小时后失效。</p>
            </div>
            <div class="footer">
                <p>{{ site_name }} 团队</p>
            </div>
        </div>
    </body>
    </html>
    """
).strip()

DEFAULT_PASSWORD_RESET_SUBJECT = "重置您的密码 - {{ site_name }}"
DEFAULT_PASSWORD_RESET_TEXT = dedent(
    """
    您好 {{ username }}，

    我们收到了重置您密码的请求。

    请点击以下链接重置密码：
    {{ reset_url }}

    如果您没有请求重置密码，请忽略此邮件，您的密码不会被更改。

    此链接将在1小时后失效。

    ---
    {{ site_name }} 团队
    """
).strip()
DEFAULT_PASSWORD_RESET_HTML = dedent(
    """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #e74c3c; color: white; padding: 20px; text-align: center; }
            .content { padding: 20px; background: #f9f9f9; }
            .button { display: inline-block; padding: 12px 24px; background: #e74c3c; color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }
            .footer { padding: 20px; text-align: center; color: #666; font-size: 12px; }
            .warning { background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{{ site_name }}</h1>
            </div>
            <div class="content">
                <h2>您好 {{ username }}，</h2>
                <p>我们收到了重置您密码的请求。</p>
                <p>请点击下方按钮重置密码：</p>
                <a href="{{ reset_url }}" class="button">重置密码</a>
                <p>或复制以下链接到浏览器：</p>
                <p style="word-break: break-all; color: #666;">{{ reset_url }}</p>
                <div class="warning">
                    <strong>注意：</strong>如果您没有请求重置密码，请忽略此邮件，您的密码不会被更改。
                </div>
                <p style="color: #999; font-size: 14px;">此链接将在1小时后失效。</p>
            </div>
            <div class="footer">
                <p>{{ site_name }} 团队</p>
            </div>
        </div>
    </body>
    </html>
    """
).strip()
