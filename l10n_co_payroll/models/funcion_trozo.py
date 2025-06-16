# -*- coding:utf-8 -*-
from odoo import models, fields, api
from datetime import datetime,date,time,timedelta

import logging

_logger = logging.getLogger(__name__)

class FuncionTrozo(models.Model):
    _name="funcion.trozo"
    _description = "modelo para funciones por trozo"

    funcion_trozo_detalle_ids=fields.One2many("funcion.trozo.detalle","funcion_trozo_id")
    nombre = fields.Char(string="Nombre")

    def calcular(self,x):
        self.ensure_one()
        for funcion_trozo_detalle_id in self.funcion_trozo_detalle_ids:
            if x >=funcion_trozo_detalle_id.desde and x<=funcion_trozo_detalle_id.hasta:
                return funcion_trozo_detalle_id.valor_inicial+(x-funcion_trozo_detalle_id.desde)*funcion_trozo_detalle_id.valor_adicional
        return 0

    def clasificar_intervalo(self,desde,hasta):
        subintervalos=[]
        residuo={"desde":desde,"hasta":hasta}
        encontrado=False
        for funcion_trozo_detalle_id in self.funcion_trozo_detalle_ids:
            if residuo["desde"]<=residuo["hasta"] and (residuo["desde"]>=funcion_trozo_detalle_id.desde and residuo["desde"]<=funcion_trozo_detalle_id.hasta):
                subintervalo={"desde":residuo["desde"],"hasta":min(residuo["hasta"],funcion_trozo_detalle_id.hasta),"valor_inicial":funcion_trozo_detalle_id.valor_inicial,"valor_adicional":funcion_trozo_detalle_id.valor_adicional}
                residuo["desde"]=subintervalo["hasta"]+1
                subintervalos.append(subintervalo)
                encontrado=True
            elif encontrado:
                break
        return subintervalos

    def clasificar_intervalo_externo(self,desde,hasta,clases,nivel,periodo):
        subintervalos=[]
        residuo={"desde":desde,"hasta":hasta}
        encontrado=False
        for clase_i in clases[0]["clase"]:
            if residuo["desde"]<=residuo["hasta"] and (residuo["desde"]>=clase_i["desde"] and residuo["desde"]<=clase_i["hasta"]):
                if nivel>1:
                    for clase_j in clases[1]["clase"]:
                        if residuo["desde"] >= clase_j["desde"] and residuo["desde"] <= clase_j["hasta"]:
                            if nivel>2:
                                for clase_k in clases[2]["clase"]:
                                    if residuo["desde"] >= clase_k["desde"] and residuo["desde"] <= clase_k["hasta"]:
                                        if nivel>3:
                                            print("TODO")
                                        else:
                                            subintervalo = {"periodo": periodo,
                                                            "desde": residuo["desde"],
                                                            "hasta": min(residuo["hasta"],
                                                                         clase_i["hasta"],
                                                                         clase_j["hasta"],
                                                                         clase_k["hasta"]),
                                                            clases[0]["tipo"]: clase_i["tipo"],
                                                            clases[1]["tipo"]: clase_j["tipo"],
                                                            clases[2]["tipo"]: clase_k["tipo"]
                                                            }
                                            residuo["desde"] = subintervalo["hasta"] + 1
                                            subintervalos.append(subintervalo)
                            else:
                                subintervalo = {"periodo":periodo,
                                                "desde": residuo["desde"],
                                                "hasta": min(residuo["hasta"],
                                                             clase_i["hasta"],
                                                             clase_j["hasta"]),
                                                clases[0]["tipo"]: clase_i["tipo"],
                                                clases[1]["tipo"]: clase_j["tipo"]
                                                }
                                residuo["desde"] = subintervalo["hasta"] + 1
                                subintervalos.append(subintervalo)
                else:
                    subintervalo = {"periodo":periodo,
                                    "desde": residuo["desde"],
                                    "hasta": min(residuo["hasta"],
                                                 clase_i["hasta"]),
                                    clases[0]["tipo"]: clase_i["tipo"]
                                    }
                    residuo["desde"] = subintervalo["hasta"] + 1
                    subintervalos.append(subintervalo)
                    encontrado=True
            elif encontrado:
                break
        return subintervalos

class FuncionTrozoDetalle(models.Model):
    _name="funcion.trozo.detalle"
    _description = "modelo para funciones por trozo - detalle"

    funcion_trozo_id=fields.Many2one("funcion.trozo")
    desde=fields.Float(string="Desde")
    hasta=fields.Float(string="Hasta")
    valor_inicial = fields.Float(string="Valor")
    valor_adicional=fields.Float(string="Adicional")

