import { memo, useCallback, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { Components } from "react-markdown";

// ── copy-to-clipboard helper ──────────────────────────────────────────────────
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);

  return (
    <button
      type="button"
      className="md-copy-btn"
      onClick={handleCopy}
      title="复制代码"
      aria-label="复制代码"
    >
      {copied ? (
        <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor">
          <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.75.75 0 0 1 1.06-1.06L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z" />
        </svg>
      ) : (
        <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor">
          <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z" />
          <path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z" />
        </svg>
      )}
      <span>{copied ? "已复制" : "复制"}</span>
    </button>
  );
}

// ── code block with language label + copy button ──────────────────────────────
function CodeBlock({
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLElement> & { children?: React.ReactNode }) {
  const match = /language-(\w+)/.exec(className || "");
  const language = match ? match[1] : "";
  const codeText =
    typeof children === "string" ? children : String(children ?? "");

  return (
    <div className="md-code-block">
      <div className="md-code-header">
        <span className="md-code-lang">{language || "code"}</span>
        <CopyButton text={codeText.replace(/\n$/, "")} />
      </div>
      <pre className={className} {...rest}>
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

// ── remark-gfm custom components ─────────────────────────────────────────────
const MARKDOWN_COMPONENTS: Components = {
  // fenced code block → custom CodeBlock
  pre({ children, ...rest }) {
    // when a pre contains exactly one code element, delegate to CodeBlock
    const codeEl =
      Array.isArray(children) ? children[0] : children;
    if (
      codeEl &&
      typeof codeEl === "object" &&
      "props" in codeEl
    ) {
      const { className, children: codeChildren } = (codeEl as React.ReactElement<{ className?: string; children?: React.ReactNode }>).props;
      return (
        <CodeBlock className={className}>
          {codeChildren}
        </CodeBlock>
      );
    }
    return <pre {...rest}>{children}</pre>;
  },

  // inline code
  code({ className, children, ...rest }) {
    const isBlock = /language-/.test(className || "");
    if (isBlock) {
      return <code className={className} {...rest}>{children}</code>;
    }
    return <code className="md-inline-code" {...rest}>{children}</code>;
  },

  // open links in new tab safely
  a({ href, children, ...rest }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" {...rest}>
        {children}
      </a>
    );
  },

  // GFM task list checkbox – make it look nice but non-interactive
  input({ type, checked, ...rest }) {
    if (type === "checkbox") {
      return (
        <input
          type="checkbox"
          checked={checked}
          readOnly
          className="md-task-checkbox"
          {...rest}
        />
      );
    }
    return <input type={type} {...rest} />;
  },
};

// ── main export ───────────────────────────────────────────────────────────────
interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export const MarkdownRenderer = memo(function MarkdownRenderer({
  content,
  className,
}: MarkdownRendererProps) {
  return (
    <div className={`md-body${className ? ` ${className}` : ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={MARKDOWN_COMPONENTS}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});
