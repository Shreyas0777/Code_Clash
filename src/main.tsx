import { StrictMode } from 'react';import { createRoot } from 'react-dom/client';import { DigitalTwinModule } from './DigitalTwinModule';import './styles.css';
createRoot(document.getElementById('root')!).render(<StrictMode><DigitalTwinModule/></StrictMode>);
