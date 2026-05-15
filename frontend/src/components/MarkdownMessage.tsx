import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";

interface Props {
  text: string;
}

/**
 * Renders an assistant reply with full markdown support:
 * GFM tables, task lists, strikethrough, fenced code blocks (with syntax
 * highlight), nested lists, blockquotes. Headings and links are styled to
 * sit naturally inside a chat bubble — no h1 / no jarring sizes.
 */
export function MarkdownMessage({ text }: Props) {
  return (
    <div className="markdown-body text-gray-900 leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
          h1: ({ children }) => (
            <h3 className="text-lg font-semibold text-gray-900 mt-4 mb-2">{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="text-lg font-semibold text-gray-900 mt-4 mb-2">{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="text-base font-semibold text-gray-900 mt-3 mb-2">{children}</h4>
          ),
          h4: ({ children }) => (
            <h5 className="text-sm font-semibold text-gray-900 mt-3 mb-1">{children}</h5>
          ),
          ul: ({ children }) => (
            <ul className="my-2 ml-5 list-disc space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-2 ml-5 list-decimal space-y-1">{children}</ol>
          ),
          li: ({ children }) => <li className="text-gray-900">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-gray-900">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand-blue hover:underline"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-3 pl-4 border-l-4 border-brand-blue/30 text-gray-700 italic">
              {children}
            </blockquote>
          ),
          code: ({ inline, children, ...rest }: any) =>
            inline ? (
              <code className="px-1.5 py-0.5 rounded bg-gray-100 text-brand-blue text-[0.92em] font-mono">
                {children}
              </code>
            ) : (
              <code className="block font-mono text-sm" {...rest}>
                {children}
              </code>
            ),
          pre: ({ children }) => (
            <pre className="my-3 p-3 rounded-md bg-gray-900 text-gray-100 overflow-x-auto text-sm scrollbar-thin">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-md border border-gray-200">
              <table className="min-w-full text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-gray-50 text-gray-700">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 text-left font-semibold border-b border-gray-200">
              {children}
            </th>
          ),
          tr: ({ children }) => (
            <tr className="border-b border-gray-100 last:border-0">{children}</tr>
          ),
          td: ({ children }) => <td className="px-3 py-2 align-top">{children}</td>,
          hr: () => <hr className="my-4 border-gray-200" />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
