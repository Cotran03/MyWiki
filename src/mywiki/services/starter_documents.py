from dataclasses import dataclass

from ..models import Document, User, Wiki
from .documents import create_document


@dataclass(frozen=True, slots=True)
class StarterDocument:
    title: str
    body_markdown: str
    tags: str


STARTER_DOCUMENTS = (
    StarterDocument(
        title="MyWiki 사용법",
        tags="시작하기, MyWiki",
        body_markdown="""
# MyWiki에 오신 것을 환영합니다

MyWiki는 나만의 문서를 정리하고, 필요한 문서만 다른 회원과 공유하는 개인 위키입니다.
새 문서는 기본적으로 나만 볼 수 있습니다.

## 문서 작성하기

1. 화면의 **새 문서**를 누릅니다.
2. 제목과 내용을 입력하고, 필요하면 쉼표로 구분한 태그를 추가합니다.
3. **미리보기**에서 표시될 모습을 확인합니다.
4. **저장**을 누릅니다.

편집 중에는 `Ctrl+S`를 눌러 빠르게 저장할 수 있습니다. 저장할 때마다 변경 이력이 새 revision으로 남습니다.

## 문서 찾기

- 상단 검색창에서 제목, 본문, 태그를 검색할 수 있습니다.
- 어느 화면에서든 `/` 키를 누르면 검색창으로 바로 이동합니다.
- 태그를 선택하면 같은 태그가 붙은 문서를 찾을 수 있습니다.

## 문서 공유하기

문서 화면의 **공유**에서 다른 회원에게 문서별 권한을 줄 수 있습니다.

- `viewer`: 문서를 읽을 수 있습니다.
- `editor`: 문서를 읽고 편집할 수 있습니다.

공유 설정과 권한 회수, 변경 이력 복구, 휴지통 관리는 문서 소유자만 할 수 있습니다.

## 변경 이력과 휴지통

- **이력**에서 이전 revision의 내용을 확인하고 현재 버전으로 복구할 수 있습니다.
- 삭제한 문서는 휴지통으로 이동하며 30일 동안 복구할 수 있습니다.
- 휴지통에 있는 문서는 공유받은 회원이 볼 수 없습니다.

## 화면 설정

상단의 테마 버튼에서 라이트, 다크, 자동 모드를 선택할 수 있습니다.

이 문서는 자유롭게 수정하거나 휴지통으로 옮겨도 됩니다. Markdown 문법은 **Markdown 사용법** 문서에서 확인하세요.
""".strip(),
    ),
    StarterDocument(
        title="Markdown 사용법",
        tags="시작하기, Markdown",
        body_markdown="""
# Markdown 사용법

Markdown은 기호를 이용해 문서 구조와 강조를 간단하게 표현하는 문법입니다. 편집 화면의 **미리보기**에서 결과를 확인할 수 있습니다.

## 제목

줄 앞에 `#`을 붙입니다. `#` 개수가 많을수록 작은 하위 제목이 됩니다.

```markdown
# 가장 큰 제목
## 두 번째 단계 제목
### 세 번째 단계 제목
```

## 강조

```markdown
**굵게 표시**
*기울여 표시*
```

MyWiki는 CommonMark 문법을 사용하므로 굵게와 기울임을 지원하지만, 취소선은 지원하지 않습니다.

## 목록

순서 없는 목록은 `-`, 순서 있는 목록은 숫자로 시작합니다.

```markdown
- 첫 번째 항목
- 두 번째 항목
  - 들여쓴 항목

1. 첫 번째 단계
2. 두 번째 단계
```

## 링크와 인용문

```markdown
[MyWiki 링크](https://example.com)

> 중요한 문장이나 다른 글을 인용할 때 사용합니다.
```

## 코드

짧은 코드는 백틱 한 쌍으로 감쌉니다: `print("Hello")`

여러 줄 코드는 백틱 세 개로 감쌉니다.

````markdown
```python
def hello():
    print("Hello")
```
````

## 문단과 구분선

문단 사이에 빈 줄을 하나 둡니다. 구분선은 하이픈 세 개로 만듭니다.

```markdown
첫 번째 문단입니다.

두 번째 문단입니다.

---
```

## 알아두기

- 원시 HTML은 보안을 위해 실행되지 않습니다.
- 표와 취소선 같은 확장 문법은 지원하지 않습니다.
- 내용을 저장하기 전에 미리보기로 결과를 확인해 보세요.

이 문서 자체를 편집하면서 문법을 직접 연습해도 좋습니다.
""".strip(),
    ),
)


def create_starter_documents(wiki: Wiki, owner: User) -> list[Document]:
    """Add the starter documents without committing the caller's transaction."""
    return [
        create_document(
            wiki,
            owner,
            title=starter.title,
            body_markdown=starter.body_markdown,
            tags=starter.tags,
            summary="기본 문서 생성",
            commit=False,
        )
        for starter in STARTER_DOCUMENTS
    ]
