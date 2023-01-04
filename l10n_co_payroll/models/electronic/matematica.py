from datetime import date, time, datetime, timedelta
import calendar

UNIDADES = (
    '',
    'UN ',
    'DOS ',
    'TRES ',
    'CUATRO ',
    'CINCO ',
    'SEIS ',
    'SIETE ',
    'OCHO ',
    'NUEVE ',
    'DIEZ ',
    'ONCE ',
    'DOCE ',
    'TRECE ',
    'CATORCE ',
    'QUINCE ',
    'DIECISEIS ',
    'DIECISIETE ',
    'DIECIOCHO ',
    'DIECINUEVE ',
    'VEINTE '
)
DECENAS = (
    'VENTI',
    'TREINTA ',
    'CUARENTA ',
    'CINCUENTA ',
    'SESENTA ',
    'SETENTA ',
    'OCHENTA ',
    'NOVENTA ',
    'CIEN '
)
CENTENAS = (
    'CIENTO ',
    'DOSCIENTOS ',
    'TRESCIENTOS ',
    'CUATROCIENTOS ',
    'QUINIENTOS ',
    'SEISCIENTOS ',
    'SETECIENTOS ',
    'OCHOCIENTOS ',
    'NOVECIENTOS '
)


def amount_to_text_es(number_in):
    converted = ''
    converted_dec = ''

    if type(number_in) != 'str':
        number = str(number_in)
    else:
        number = number_in

    number_str = number

    try:
        number_int, number_dec = number_str.split(".")
    except ValueError:
        number_int = number_str
        number_dec = "00"

    number_str = number_int.zfill(9)
    millones = number_str[:3]
    miles = number_str[3:6]
    cientos = number_str[6:]

    if millones:
        if millones == '001':
            converted += 'UN MILLON '
        elif int(millones) > 0:
            converted += '%sMILLONES ' % __convertNumber(millones)

    if miles:
        if miles == '001':
            converted += 'MIL '
        elif int(miles) > 0:
            converted += '%sMIL ' % __convertNumber(miles)
    if cientos:
        if cientos == '001':
            converted += 'UN '
        elif int(cientos) > 0:
            converted += '%s ' % __convertNumber(cientos)

    if number_dec != "00" and number_dec != "0":
        number_dec = number_dec.zfill(3)
        converted_dec += '%s ' % __convertNumber(number_dec)

    return converted, converted_dec


def __convertNumber(n):
    output = ''

    if n == '100':
        output = "CIEN "
    elif n[0] != '0':
        output = CENTENAS[int(n[0]) - 1]

    k = int(n[1:])
    if k <= 20:
        output += UNIDADES[k]
    else:
        if (k > 30) & (n[2] != '0'):
            output += '%sY %s' % (DECENAS[int(n[1]) - 2], UNIDADES[int(n[2])])
        else:
            output += '%s%s' % (DECENAS[int(n[1]) - 2], UNIDADES[int(n[2])])

    return output


def duracion360(desde, hasta):
    dia_hasta = hasta.day
    mes_hasta = hasta.month
    anio_hasta = hasta.year
    if (desde.day == hasta.day and desde.month == hasta.month and desde.year == hasta.year):
        return 1
    dia_hasta_corregido = dia_hasta
    if mes_hasta == 2:
        if calendar.isleap(anio_hasta):
            if dia_hasta == 29:
                dia_hasta_corregido = 30
        else:
            if dia_hasta == 28:
                dia_hasta_corregido = 30
    return (anio_hasta - desde.year) * 360 + (mes_hasta - desde.month) * 30 + (
            min(dia_hasta_corregido, 30) - desde.day) + 1


def clasificar_intervalo(desde, hasta, clases, nivel, periodo, unidad):
    subintervalos = []
    residuo = {"desde": desde, "hasta": hasta}
    encontrado = False
    for clase_i in clases[0]["clase"]:
        # print(f"residuo_externo:{residuo}")
        if residuo["desde"] <= residuo["hasta"] and (
                residuo["desde"] >= clase_i["desde"] and residuo["desde"] <= clase_i["hasta"]):
            if nivel > 1:
                for clase_j in clases[1]["clase"]:
                    # print(f"residuo_interno:{residuo}")
                    if residuo["desde"] >= clase_j["desde"] and residuo["desde"] <= clase_j["hasta"]:
                        if nivel > 2:
                            for clase_k in clases[2]["clase"]:
                                if residuo["desde"] >= clase_k["desde"] and residuo["desde"] <= clase_k["hasta"]:
                                    if nivel > 3:
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
                                        residuo["desde"] = subintervalo["hasta"] + unidad
                                        subintervalos.append(subintervalo)
                        else:
                            subintervalo = {"periodo": periodo,
                                            "desde": residuo["desde"],
                                            "hasta": min(residuo["hasta"],
                                                         clase_i["hasta"],
                                                         clase_j["hasta"]),
                                            clases[0]["tipo"]: clase_i["tipo"],
                                            clases[1]["tipo"]: clase_j["tipo"]
                                            }
                            residuo["desde"] = subintervalo["hasta"] + unidad
                            # print(f"subintervalo:{subintervalo}")
                            subintervalos.append(subintervalo)
            else:
                subintervalo = {"periodo": periodo,
                                "desde": residuo["desde"],
                                "hasta": min(residuo["hasta"],
                                             clase_i["hasta"]),
                                clases[0]["tipo"]: clase_i["tipo"]
                                }
                residuo["desde"] = subintervalo["hasta"] + unidad
                subintervalos.append(subintervalo)
                encontrado = True
        elif encontrado:
            break
    return subintervalos


def obtener_intervalos_clasificados(fecha_desde, fecha_hasta, partes_dia, horario):
    print(f"fecha_desde:{fecha_desde}")
    print(f"fecha_hasta:{fecha_hasta}")
    dias = (fecha_hasta - fecha_desde).days + 1
    # print("dias:",dias)
    fechas = [fecha_desde.date() + timedelta(days=i) for i in range(0, dias)]
    clases = [{"tipo": "t_parte_dia", "clase": partes_dia}, {"tipo": "t_parte_jornada"}]
    nivel = 2
    unidad = timedelta(seconds=1)
    intervalos = []
    print("aaaaaaaaaaaaaaa")
    for fecha in fechas:
        # Para cada fecha se obtiene el partes_jornada
        # Se saca el week_type con week%2
        # Se saca el dayofweek con int(fecha.strftime("%u"))-1
        week_type = str(int(fecha.strftime("%U")) % 2)
        dayofweek = str(int(fecha.strftime("%u")) - 1)
        print("00000000")
        if horario["tipo"] == "semanal":
            entradas_horario_fecha = [(entrada_horario["hour_from"], entrada_horario["hour_to"]) for entrada_horario in
                                      horario["entradas_horario"] if
                                      entrada_horario["dayofweek"] == dayofweek]
        elif horario["tipo"] == "bisemanal":
            entradas_horario_fecha = [(entrada_horario["hour_from"], entrada_horario["hour_to"]) for entrada_horario in
                                      horario["entradas_horario"] if
                                      entrada_horario["dayofweek"] == dayofweek and entrada_horario[
                                          "week_type"] == week_type]
        elif horario["tipo"] == "fechas":
            ##Tomamos la ultima fecha  previa o igual a la fecha actual.
            # fecha_actualizacion = max(entrada_horario["fecha"] for entrada_horario in horario["entradas_horario"] if
            #                          entrada_horario["fecha"]<=fecha)
            entradas_horario_fecha = [(entrada_horario["hour_from"], entrada_horario["hour_to"]) for entrada_horario in
                                      horario["entradas_horario"] if
                                      entrada_horario["fecha"] == fecha]
        print("2222222")

        partes_jornada = partir_dia(entradas_horario_fecha)
        # print(f"partes_jornada:{partes_jornada}")
        clases[1].update({"clase": partes_jornada})
        ##################################
        if fecha == fecha_desde.date() and fecha == fecha_hasta.date():
            hora_desde = timedelta(hours=fecha_desde.time().hour, minutes=fecha_desde.time().minute,
                                   seconds=fecha_desde.time().second)
            hora_hasta = timedelta(hours=fecha_hasta.time().hour, minutes=fecha_hasta.time().minute,
                                   seconds=fecha_hasta.time().second)
        elif fecha == fecha_desde.date() and fecha < fecha_hasta.date():
            # Hay mas de un dia y estamos en el primer dia.
            hora_desde = timedelta(hours=fecha_desde.time().hour, minutes=fecha_desde.time().minute,
                                   seconds=fecha_desde.time().second)
            hora_hasta = timedelta(hours=23, minutes=59, seconds=59)
        elif fecha > fecha_desde.date() and fecha < fecha_hasta.date():
            # Hay mas de dos dias y estamos en un dia intermedio.
            hora_desde = timedelta(hours=0)
            hora_hasta = timedelta(hours=23, minutes=59, seconds=59)
        elif fecha > fecha_desde.date() and fecha == fecha_hasta.date():
            # Hay mas de un dia y estamos en el ultimo dia.
            hora_desde = timedelta(hours=0)
            hora_hasta = timedelta(hours=fecha_hasta.time().hour, minutes=fecha_hasta.time().minute,
                                   seconds=fecha_hasta.time().second)
        periodo = fecha
        intervalos_unidad = clasificar_intervalo(hora_desde, hora_hasta, clases, nivel, periodo, unidad)
        print(f"intervalos_unidad:{intervalos_unidad}")
        intervalos += intervalos_unidad
    return [intervalo for intervalo in intervalos if intervalo["hasta"] > intervalo["desde"]]


def partir_dia(intervalos):
    intervalos_dia = []
    fin_anterior = 0
    for intervalo in intervalos:
        if fin_anterior < intervalo[0]:
            dic_intervalo_extra = {"desde": timedelta(seconds=fin_anterior * 3600),
                                   "hasta": timedelta(seconds=intervalo[0] * 3600 - 1), "tipo": "extra"}
            intervalos_dia.append(dic_intervalo_extra)
        dic_intervalo_laboral = {"desde": timedelta(seconds=intervalo[0] * 3600),
                                 "hasta": timedelta(seconds=intervalo[1] * 3600 - 1), "tipo": "laboral"}
        intervalos_dia.append(dic_intervalo_laboral)
        fin_anterior = intervalo[1]
    dic_intervalo_extra_final = {"desde": timedelta(seconds=fin_anterior * 3600),
                                 "hasta": timedelta(seconds=24 * 3600 - 1), "tipo": "extra"}
    intervalos_dia.append(dic_intervalo_extra_final)
    return intervalos_dia


def solapa(intervalo_comparar, lista_intervalos):
    for intervalo in lista_intervalos:
        # print(f"intervalo:{intervalo_comparar},lista_intervalos:{lista_intervalos}")
        # print(intervalo[0]<=intervalo_comparar[0]<=intervalo[1] or intervalo[0]<=intervalo_comparar[1]<=intervalo[1])
        if intervalo[0] <= intervalo_comparar[0] <= intervalo[1] or intervalo[0] <= intervalo_comparar[1] <= intervalo[
            1]:
            # print(f"intervalo:{intervalo_comparar},lista_intervalos:{lista_intervalos}")
            return True
    else:
        return False









