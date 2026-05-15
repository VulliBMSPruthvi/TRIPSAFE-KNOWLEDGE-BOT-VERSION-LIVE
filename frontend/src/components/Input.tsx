import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import { forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, hint, error, className = "", id, ...rest }, ref) => {
    const inputId = id ?? rest.name;
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-gray-700">
            {label}
          </label>
        )}
        <input
          {...rest}
          id={inputId}
          ref={ref}
          className={`h-10 px-3 rounded-md border bg-white text-gray-900 placeholder:text-gray-400 outline-none transition focus:border-brand-blue focus:ring-2 focus:ring-brand-blue/20 ${error ? "border-danger" : "border-gray-200"} ${className}`}
        />
        {error ? (
          <p className="text-xs text-danger">{error}</p>
        ) : hint ? (
          <p className="text-xs text-gray-500">{hint}</p>
        ) : null}
      </div>
    );
  },
);
Input.displayName = "Input";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, hint, error, className = "", id, ...rest }, ref) => {
    const inputId = id ?? rest.name;
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-gray-700">
            {label}
          </label>
        )}
        <textarea
          {...rest}
          id={inputId}
          ref={ref}
          className={`min-h-[96px] px-3 py-2 rounded-md border bg-white text-gray-900 placeholder:text-gray-400 outline-none transition focus:border-brand-blue focus:ring-2 focus:ring-brand-blue/20 ${error ? "border-danger" : "border-gray-200"} ${className}`}
        />
        {error ? (
          <p className="text-xs text-danger">{error}</p>
        ) : hint ? (
          <p className="text-xs text-gray-500">{hint}</p>
        ) : null}
      </div>
    );
  },
);
Textarea.displayName = "Textarea";
