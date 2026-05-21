import { FileSearch, ListChecks } from 'lucide-react';
import { useState } from 'react';
import { ClassificationPage } from './ClassificationPage';
import { ExtractionPage } from './ExtractionPage';

type Page = 'extraction' | 'classification';

export function App() {
  const [page, setPage] = useState<Page>('extraction');

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>Rules Labeling</h1>
          <p>Review extracted rules and classification fields against source text.</p>
        </div>
        <nav className="tabs" aria-label="Labeling pages">
          <button
            className={page === 'extraction' ? 'active' : ''}
            onClick={() => setPage('extraction')}
            title="Extraction labeling"
          >
            <FileSearch size={18} />
            Extraction
          </button>
          <button
            className={page === 'classification' ? 'active' : ''}
            onClick={() => setPage('classification')}
            title="Classification labeling"
          >
            <ListChecks size={18} />
            Classification
          </button>
        </nav>
      </header>
      {page === 'extraction' ? <ExtractionPage /> : <ClassificationPage />}
    </div>
  );
}
