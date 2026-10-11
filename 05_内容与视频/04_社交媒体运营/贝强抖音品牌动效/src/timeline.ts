export const FPS=24;
export const TOTAL_FRAMES=624;
type Scene={id:string;frames:number;from:number;src:string;title:string;sub?:string;video?:boolean;sourceFrame?:number;dark?:boolean;detail?:boolean;immediate?:boolean};
export const TIMELINE:Scene[]=[
  {
    "id": "opening",
    "frames": 72,
    "src": "sock-hero.png",
    "title": "针织袜子鞋",
    "from": 0
  },
  {
    "id": "knit",
    "frames": 36,
    "src": "sock-knit.png",
    "title": "立体织纹",
    "dark": true,
    "from": 72
  },
  {
    "id": "touch",
    "frames": 72,
    "src": "dynamic/tactile.mp4",
    "title": "指尖，触到织纹",
    "video": true,
    "sourceFrame": 0,
    "from": 108
  },
  {
    "id": "collar",
    "frames": 36,
    "src": "campaign-collar.png",
    "title": "袜式鞋口",
    "sub": "免系带 · 套脚结构",
    "from": 180
  },
  {
    "id": "entry",
    "frames": 36,
    "src": "dynamic/donning-clean.mp4",
    "title": "套上，就出发",
    "video": true,
    "sourceFrame": 0,
    "from": 216
  },
  {
    "id": "entry-detail",
    "frames": 18,
    "src": "campaign-collar.png",
    "title": "套上，就出发",
    "detail": true,
    "immediate": true,
    "from": 252
  },
  {
    "id": "entry-finish",
    "frames": 18,
    "src": "dynamic/donning-clean.mp4",
    "title": "套上，就出发",
    "video": true,
    "sourceFrame": 102,
    "immediate": true,
    "from": 270
  },
  {
    "id": "walk",
    "frames": 144,
    "src": "dynamic/walking.mp4",
    "title": "穿进日常",
    "sub": "一路，自在一点",
    "video": true,
    "sourceFrame": 0,
    "from": 288
  },
  {
    "id": "rest",
    "frames": 48,
    "src": "dynamic/settling.mp4",
    "title": "起身，再出发",
    "video": true,
    "sourceFrame": 48,
    "from": 432
  },
  {
    "id": "pair",
    "frames": 72,
    "src": "campaign-overhead.png",
    "title": "针织 · 套脚 · 日常",
    "from": 480
  },
  {
    "id": "closing",
    "frames": 72,
    "src": "campaign-product.png",
    "title": "贝强",
    "from": 552
  }
];
