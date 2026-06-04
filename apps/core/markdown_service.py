"""
Markdown渲染服务
"""
import markdown
import bleach
from apps.core.link_formatter import apply_default_external_link_attributes
from apps.core.extensions.formatter_service import apply_extension_formatters


class MarkdownService:
    """Markdown渲染服务"""

    # 允许的HTML标签
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 's', 'del', 'ins',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'blockquote', 'code', 'pre',
        'ul', 'ol', 'li',
        'a', 'img',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'hr',
        'div', 'span',
    ]

    # 允许的HTML属性
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title', 'target', 'rel'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'code': ['class'],
        'pre': ['class'],
        'div': ['class'],
        'span': ['class'],
        'td': ['align'],
        'th': ['align'],
    }

    # 允许的协议
    ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

    @staticmethod
    def render(content: str, sanitize: bool = True) -> str:
        """
        渲染Markdown为HTML

        Args:
            content: Markdown内容
            sanitize: 是否清理HTML（防止XSS）

        Returns:
            str: HTML内容
        """
        if not content:
            return ''

        # 配置Markdown扩展
        extensions = [
            'markdown.extensions.extra',  # 表格、代码块等
            'markdown.extensions.codehilite',  # 代码高亮
            'markdown.extensions.nl2br',  # 换行转<br>
            'markdown.extensions.sane_lists',  # 更好的列表支持
            'markdown.extensions.toc',  # 目录
            'markdown.extensions.fenced_code',  # 围栏代码块
            'markdown.extensions.tables',  # 表格
        ]

        # 扩展配置
        extension_configs = {
            'markdown.extensions.codehilite': {
                'css_class': 'highlight',
                'linenums': False,
            },
            'markdown.extensions.toc': {
                'permalink': True,
            }
        }

        # 渲染Markdown
        md = markdown.Markdown(
            extensions=extensions,
            extension_configs=extension_configs,
            output_format='html5'
        )

        html = md.convert(content)

        # 处理外部链接
        html = MarkdownService._process_external_links(html)

        # 允许扩展对最终 HTML 再做一轮变换，例如 emoji/twemoji 渲染
        html = apply_extension_formatters(html)

        # 清理HTML（防止XSS）
        if sanitize:
            html = bleach.clean(
                html,
                tags=MarkdownService.ALLOWED_TAGS,
                attributes=MarkdownService.ALLOWED_ATTRIBUTES,
                protocols=MarkdownService.ALLOWED_PROTOCOLS,
                strip=True
            )

        return html

    @staticmethod
    def _process_external_links(html: str) -> str:
        """
        处理外部链接，添加target="_blank"和rel="noopener"

        Args:
            html: HTML内容

        Returns:
            str: 处理后的HTML
        """
        return apply_default_external_link_attributes(html)

    @staticmethod
    def strip_html(html: str) -> str:
        """
        移除HTML标签，获取纯文本

        Args:
            html: HTML内容

        Returns:
            str: 纯文本
        """
        return bleach.clean(html, tags=[], strip=True)

    @staticmethod
    def get_excerpt(content: str, length: int = 200) -> str:
        """
        获取内容摘要

        Args:
            content: Markdown内容
            length: 摘要长度

        Returns:
            str: 摘要文本
        """
        # 渲染为HTML
        html = MarkdownService.render(content, sanitize=True)

        # 移除HTML标签
        text = MarkdownService.strip_html(html)

        # 截取指定长度
        if len(text) > length:
            text = text[:length] + '...'

        return text

    @staticmethod
    def validate_markdown(content: str) -> bool:
        """
        验证Markdown内容

        Args:
            content: Markdown内容

        Returns:
            bool: 是否有效
        """
        if not content or not content.strip():
            return False

        # 检查长度
        if len(content) > 100000:  # 最大100KB
            return False

        return True
