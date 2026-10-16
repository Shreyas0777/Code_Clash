export type Mode = 'normal' | 'energy' | 'anomaly' | 'carbon';
export type Building = { id:string; name:string; category:string; position:[number,number,number]; energy:number; carbon:number; anomaly:boolean; recommendation:string; history:{time:string; value:number; forecast?:number}[] };
export type Scenario = { kind:'HVAC schedule'|'LED retrofit'|'Equipment hours'; value:number };
