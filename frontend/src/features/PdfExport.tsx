import { useContext } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ArrowDownToLine } from 'lucide-react';
import { Auth, ErrorBox } from '../components/ui';
import { api } from '../lib/api';

export default function PdfExport({ filters, label = 'Export PDF' }: { filters: string; label?: string }) {
  const { user } = useContext(Auth);
  const download = useMutation({ mutationFn: async () => {
    const blob = await api<Blob>('/reports/complaints.pdf?' + filters, {}, 'blob');
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = 'onecase-complaints.pdf';
    document.body.appendChild(link); link.click(); link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } });
  if (!user.capabilities.export_register) return null;
  return <div><button className="button secondary small" disabled={download.isPending} onClick={() => download.mutate()}><ArrowDownToLine size={15} />{download.isPending ? 'Preparing PDF…' : label}</button><ErrorBox error={download.error} /></div>;
}
