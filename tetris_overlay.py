
import pygame
from tetris_config import CONFIG

class Overlay:
    def __init__(self):
        self.active=False
        self.items=[
            ("CELL_SIZE","Cell size",16,48,2),
            ("DAS_MS","DAS",0,400,10),
            ("ARR_MS","ARR",0,200,5),
            ("LOCK_DELAY_MS","LockDelay",100,2000,25),
            ("GRAVITY_MULT","Grav×",0.2,5.0,0.1),
            ("SOFT_DROP_MULT","Soft×",0.5,5.0,0.1),
            ("NES_FIRST_PIECE_AVOID_SZO","No SZO first",False,True,None),
        ]
        self.index=0

    def toggle(self): self.active=not self.active

    def handle(self,e):
        if e.key in (pygame.K_ESCAPE,pygame.K_F1): self.toggle(); return
        if e.key==pygame.K_UP: self.index=(self.index-1)%len(self.items); return
        if e.key==pygame.K_DOWN: self.index=(self.index+1)%len(self.items); return
        key,label,lo,hi,step=self.items[self.index]
        val=CONFIG[key]
        if isinstance(lo,(int,float)):
            if e.key==pygame.K_LEFT: CONFIG[key]=max(lo,val-step)
            if e.key==pygame.K_RIGHT: CONFIG[key]=min(hi,val+step)
        else:
            if e.key in (pygame.K_RETURN,pygame.K_LEFT,pygame.K_RIGHT): CONFIG[key]=not CONFIG[key]

    def draw(self,screen,font,w,h):
        if not self.active: return
        s=pygame.Surface((w-80,h-80),pygame.SRCALPHA); s.fill((20,25,40,230))
        screen.blit(s,(40,40))
        y=80
        for i,(key,label,lo,hi,step) in enumerate(self.items):
            col=(255,255,255) if i==self.index else (200,210,235)
            v=CONFIG[key]
            txt=f"{label}: {v}"
            screen.blit(font.render(txt,True,col),(60,40+y)); y+=30
