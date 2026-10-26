import { Children, cloneElement, createContext, isValidElement, useContext, useId, type FormEvent, type ReactNode, type ReactElement } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertCircle, RefreshCw, FolderOpen, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { api, label, date, type User, type Page } from '../lib/api';

export const Auth = createContext<{ user: User; logout: () => void }>(null!);
export const Toast = createContext<(message: string) => void>(() => {});
export const useData = <T,>(path: string) => useQuery({ queryKey: [path], queryFn: () => api<T>(path) });

export function ErrorBox({ error, retry }: { error: Error | null; retry?: () => void }) {
  return error ? <div className="error" role="alert"><AlertCircle size={18} /><span>{error.message}</span>{retry && <button className="text-button" onClick={retry}>Retry</button>}</div> : null;
}
export function Loading() { return <div className="loading" role="status"><RefreshCw className="spin" size={20} /> Loading workspace…</div>; }
export function Empty({ title = 'No records to show', children }: { title?: string; children?: ReactNode }) { return <div className="empty"><FolderOpen size={32} /><h3>{title}</h3><p>{children || 'Records in your authorized scope will appear here.'}</p></div>; }
export function Badge({ value, tone }: { value: string; tone?: string }) { return <span className={`badge ${tone || value}`}>{label(value)}</span>; }
export function Modal({ title, description, trigger, children, open, onOpenChange }: { title: string; description: string; trigger?: ReactNode; children: ReactNode; open?: boolean; onOpenChange?: (open: boolean) => void }) {
  return <Dialog.Root open={open} onOpenChange={onOpenChange}>{trigger && <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>}<Dialog.Portal><Dialog.Overlay className="overlay" /><Dialog.Content className="dialog"><div className="dialog-heading"><div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description></div><Dialog.Close className="icon-button" aria-label="Close dialog"><X size={20} /></Dialog.Close></div>{children}</Dialog.Content></Dialog.Portal></Dialog.Root>;
}
export function useSave<T>(fn: (data: T) => Promise<unknown>, onSuccess?: () => void) {
  const client = useQueryClient(); const toast = useContext(Toast);
  return useMutation({ mutationFn: fn, onSuccess: async () => { await client.invalidateQueries(); toast('Changes saved successfully'); onSuccess?.(); } });
}
export function Heading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="muted">{description}</p></div>{action}</div>;
}
export function FormError({ mutation }: { mutation: { error: Error | null } }) { return <ErrorBox error={mutation.error} />; }
export function Field({ title, children, hint }: { title: string; children: ReactNode; hint?: string }) {
  const id = useId();
  const decorate = (nodes: ReactNode): ReactNode => Children.map(nodes, node => {
    if (!isValidElement(node)) return node;
    const element = node as ReactElement<{children?: ReactNode; id?: string; 'aria-labelledby'?: string; 'aria-describedby'?: string}>;
    if (['input', 'select', 'textarea'].includes(String(element.type))) return cloneElement(element, {id: id + '-control', 'aria-labelledby': id, 'aria-describedby': hint ? id + '-hint' : undefined});
    return element.props.children ? cloneElement(element, {children: decorate(element.props.children)}) : element;
  });
  return <div className="field"><label htmlFor={id + '-control'} id={id}>{title}</label>{decorate(children)}{hint && <small id={id + '-hint'}>{hint}</small>}</div>;
}
export function Pager({ page, setCursor, cursor }: { page: Page<unknown>; cursor: string | null; setCursor: (value: string | null) => void }) {
  return <div className="pager"><span>{page.total} authorized records · Updated {date(page.asOf, true)} IST</span><div>{cursor && <button className="button secondary small" onClick={() => setCursor(null)}><ChevronLeft size={14} /> First page</button>}<button className="button secondary small" disabled={!page.nextCursor} onClick={() => setCursor(String(page.nextCursor))}>Next page <ChevronRight size={14} /></button></div></div>;
}

