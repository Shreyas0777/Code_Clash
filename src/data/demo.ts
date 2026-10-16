import type { Building } from '../types';
const times=['08:00','10:00','12:00','14:00','16:00','18:00','20:00'];
const make=(base:number,rise:number)=>times.map((time,index)=>({time,value:Math.round(base+rise*Math.sin((index+1)*.7)+index*5),forecast:index>4?Math.round(base+rise*Math.sin((index+1)*.7)+index*5+8):undefined}));
export const buildings:Building[]=[
 {id:'studio',name:'Studio Annex',category:'SET campus asset',position:[2.3,.35,.5],energy:498,carbon:306,anomaly:true,recommendation:'Investigate the simulated cooling-load deviation before 16:00.',history:make(408,61)},
 {id:'canopy',name:'Arrival Canopy',category:'SET campus asset',position:[.9,.35,2.3],energy:174,carbon:107,anomaly:false,recommendation:'Lighting scheduling is the next simulated intervention.',history:make(146,20)},
 {id:'office',name:'Building 124-87-117',category:'Imported campus asset',position:[-6,1.55,3.8],energy:367,carbon:225,anomaly:false,recommendation:'Simulated occupancy profile indicates an after-hours reduction opportunity.',history:make(303,34)},
 {id:'farmhouse',name:'Saltbox House',category:'Imported campus asset',position:[5.4,.75,-3.7],energy:91,carbon:56,anomaly:false,recommendation:'Simulated heating schedule can be reviewed against use hours.',history:make(70,15)},
 {id:'mansion',name:'Classical Mansion',category:'Imported campus asset',position:[5.1,1.05,3.2],energy:238,carbon:146,anomaly:false,recommendation:'Simulated envelope improvements are the next modeled opportunity.',history:make(196,25)}
];
export const campus={energy:1368,demand:1.64,carbon:840,intensity:18.6,forecast:1.78,timestamp:'16 Oct 2026, 14:30 IST'};
