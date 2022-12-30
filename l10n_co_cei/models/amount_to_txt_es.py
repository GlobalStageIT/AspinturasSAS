#!/usr/bin/python                  
# -*- coding: utf-8 -*-            

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

    number_str = number_int.zfill(10)
    miles_millones = number_str[:1]
    millones = number_str[1:4]
    miles = number_str[4:7]
    cientos = number_str[7:]

    if miles_millones:
        if miles_millones == '1':
            converted += 'MIL '
        elif int(miles_millones) > 0:
            print(UNIDADES[int(miles_millones)])
            converted += UNIDADES[int(miles_millones)] + 'MIL '

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
