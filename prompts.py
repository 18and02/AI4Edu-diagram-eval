"""Prompts from the 2026-09-25 v2 workflow."""

from typing import Any

PROMPT_TEXT = "这个图下面这个TikZ代码是我学生就照这个图写的,可能写的不对你帮我检查一下再帮我修改过来。"
STEM_PREFIX = "\n\n这道题的题干是:\n"
SHAPE_SUFFIX = ("\n\n题干只用来确定图中已有元素的准确形状、位置和数量关系。修改后的图只画原图里画出来的点、线、曲线和标注;"
                "题干提到但原图没有画出的内容(辅助线、字母、记号、方程、坐标等)一律不要加。")

Y1_PROMPT = """\
这张图下面的 TikZ 代码是照着上面这张原图写的,但它编译不过。
编译器的报错是:

{feedback}

请你先修好编译错误,让它能编译出图;在修的过程中,如果发现代码和原图对不上,一并改过来。
不要为了能编译而删掉原图里本来就有的图形元素。"""

Y2_A_PROMPT = """\
这张图下面的 TikZ 代码是照着上面这张原图写的,但它没有写完 ——
模型写到一半开始重复同一行,然后被长度上限截断了,所以这份代码是残缺的。

请你照着原图重新写一份完整的 TikZ。
前面没有重复的那部分如果和原图对得上,可以拿来用;重复的那些行直接丢掉。
以原图为准,不要照抄这份残缺代码里的错误。"""

Y2_B_PROMPT = """\
这张图下面的 TikZ 代码是照着上面这张原图写的,但它只声明了一堆坐标,
没有画任何图形,所以渲染出来是空白的。

请你照着原图重新写一份完整的 TikZ,把图真正画出来。
以原图为准。"""

COMMON_TAIL = r"""

输出要求:
1. 只输出一份完整的、可直接编译的 LaTeX 文档,从 \documentclass 开始,到 \end{document} 结束。
2. 你用到的每一个 TikZ 库都必须写出对应的 \usetikzlibrary,不要省略。
3. 不要输出 Markdown 代码围栏,不要输出任何解释文字。
4. 不允许只声明坐标而不画图。图里必须有实际的 \draw / \node 等绘制命令。"""

RETRY_PREFIX = """

这是第 {attempt} 次尝试。上一版你给的代码是:

"""

RETRY_SUFFIX = """

它仍然没通过,原因见上。请针对这个原因改。"""

BLANK_FEEDBACK = "上一版能编译但渲染出来是空白的"

EMPTY_SHELL_FEEDBACK = "上一版只声明了坐标,没有任何 \\draw / \\node"

def base_prompt(route: str, variant: str | None, feedback: str | None) -> str:
    if route == "Y1":
        if not feedback:
            raise ValueError("Y1 prompt requires compile/render feedback")
        return Y1_PROMPT.format(feedback=feedback)
    if route != "Y2" or variant not in {"A", "B"}:
        raise ValueError("invalid route/variant")
    prompt = Y2_A_PROMPT if variant == "A" else Y2_B_PROMPT
    if feedback:
        prompt += f"\n\n上一版的失败原因是:\n\n{feedback}"
    return prompt

def request_text_parts(
    item: dict[str, Any],
    attempt: int,
    attached_code: str,
    feedback: str | None,
) -> list[str]:
    prompt = base_prompt(item["route"], item.get("variant"), feedback)
    if attempt == 1:
        return [prompt, attached_code, COMMON_TAIL]
    return [
        prompt + RETRY_PREFIX.format(attempt=attempt),
        attached_code,
        RETRY_SUFFIX + COMMON_TAIL,
    ]
