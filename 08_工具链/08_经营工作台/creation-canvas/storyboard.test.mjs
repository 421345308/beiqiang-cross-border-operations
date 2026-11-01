import test from 'node:test';
import assert from 'node:assert/strict';
import {addShot,exportBrief} from './storyboard.mjs';
test('shot appends independently and brief carries production fields and relationships',()=>{
 const original=[{id:'asset',data:{title:'实物参考',media_path:'05_内容与视频/ref.png'}}];
 const shot=addShot(original,'shot');shot.data.purpose='展示鞋底';shot.data.duration='4';shot.data.visual='侧面近景';
 assert.equal(original.length,1);assert.equal(shot.data.kind,'shot');
 const brief=exportBrief('项目',[...original,shot],[{source:'asset',target:'shot'}]);
 for(const value of ['展示鞋底','时长（秒）：4','侧面近景','05_内容与视频/ref.png','实物参考 → 镜头 1'])assert.ok(brief.includes(value));
});
