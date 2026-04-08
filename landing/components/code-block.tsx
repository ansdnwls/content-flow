import { CodeLine } from "@/lib/site-data";

type CodeBlockProps = {
  label: string;
  language: string;
  code: CodeLine[];
};

export function CodeBlock({ label, language, code }: CodeBlockProps) {
  return (
    <div className="code-shell">
      <div className="code-shell__header">
        <span className="code-shell__pill">{label}</span>
        <span className="code-shell__lang">{language}</span>
      </div>
      <pre className="code-shell__body">
        <code>
          {code.map((line, lineIndex) => (
            <div className="code-shell__line" key={`${label}-${lineIndex}`}>
              <span className="code-shell__line-number">{String(lineIndex + 1).padStart(2, "0")}</span>
              <span className="code-shell__line-content">
                {line.length === 0 ? (
                  <br />
                ) : (
                  line.map((token, tokenIndex) => (
                    <span className={`token token--${token.kind ?? "plain"}`} key={`${lineIndex}-${tokenIndex}`}>
                      {token.value}
                    </span>
                  ))
                )}
              </span>
            </div>
          ))}
        </code>
      </pre>
    </div>
  );
}
