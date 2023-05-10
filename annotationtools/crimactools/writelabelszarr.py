import time
from timeit import timeit

import zarr
import xarray as xr
import math
import numpy as np
from numcodecs import Blosc
import pyarrow.parquet as pq
import dask.array as dask
import datetime
import csv
import sys
import subprocess
import os

#  to run on pallas.hi.no activate the crimac conda environment
#  source /localscratch_hdd/tomasz/anaconda3/
#  conda activate crimac


shipID="847"
rawfile = '/Users/tf/work/crimac/test/out/test1.zarr'
parquetfile2 = '/Users/tf/work/crimac/test/out/test1_work.parquet'
savefile2 = '/Users/tf/work/crimac/test/out/out_annot7600hck2.zarr'


# chunk size for ping dimension
pingchunk = 20000
rangechunk = 2643


if("-shipID" in  sys.argv):
    shipID = str(sys.argv[sys.argv.index("-shipID") + 1])
if("-rawfile" in  sys.argv):
    rawfile = sys.argv[sys.argv.index("-rawfile") + 1]
if("-parquet" in  sys.argv):
    parquetfile2  = sys.argv[sys.argv.index("-parquet") + 1]
if("-savefile" in  sys.argv):
    savefile2 = sys.argv[sys.argv.index("-savefile") + 1]
if("-pings" in  sys.argv):
    pingchunk = int(sys.argv[sys.argv.index("-pings") + 1])


# Create annotation zarr for chunk
#
def write_annot(rawzarrfile,allobjects,start,end,rangeend,savefile,writemode  ):
    pingerror = 0
    pingok  = 0
    z = xr.open_zarr(rawzarrfile, chunks={'ping_time':'50000'})
    data1 = z.sv.isel(frequency=slice(0, 1), ping_time=slice(start, end), range=slice(0, rangeend))
    #array with pingtime
    data_ping = np.asarray(data1.ping_time)
    #array with range depth
    data_range = np.asarray(data1.range)
    dataheave = z.heave.isel( ping_time=slice(start, end))
    datatransducer = z.transducer_draft.isel(frequency=slice(0, 1), ping_time=slice(start, end))

    raw_heave = np.asarray(dataheave)
    raw_transducer = np.asarray(datatransducer)

    rawpinglist = np.asarray(data_ping)

    lsss_tmp = np.zeros([len(category),len(data_ping), len(data_range)] , dtype=np.float32)
    lsssobject_tmp = np.zeros([len(data_ping), len(data_range)], dtype=int)
    lsssobjecttype_tmp = np.zeros([len(data_ping), len(data_range)], dtype=int)
    
    lsssupperthr_tmp= np.zeros([len(data_ping) ], dtype=np.float32)
    lssslowerthr_tmp= np.zeros([len(data_ping) ], dtype=np.float32)

    objectnum={}
    objectnumcounter=1

    pingnum = 0
    hits = 0
    # loop through pings in chunk
    for pingx in rawpinglist:
        p6 =pingx
        if str(pingx).endswith("9")  :
            p6 =pingx +np.timedelta64(1, 'ns')
        if str(pingx).endswith("8")  :
            p6 =pingx +np.timedelta64(2, 'ns')
        if str(pingx).endswith("7")  :
            p6 =pingx +np.timedelta64(3, 'ns')

        p3 = str(p6).replace('T', ' ')[0:26]
        p3sec = str(pingx).replace('T', ' ')[0:19]
        #program_starts = time.time()

        # Start with priority 3 : layers
        # then priority 2 boxes
        # in the end overite alle category layers with exclude priority 1
        # workannot dictionaries are in the above order
        type=3

        for work in workannot:

            rows=[]
            if p3 in work:
                # get all the annotations in a list from the parquet file for the current ping
                rows = work[p3]
                hits = hits+1
                pingok = pingok + 1
                del work[p3]
                #print("remaining annotation pings : " + str(len(work)))
            elif p3sec in work:
                # get all the annotations in a list from the parquet file for the current ping
                rows = work[p3sec]
                hits = hits+1
                pingok = pingok + 1
                del work[p3sec]
                print(p3sec+" ping len 19 "  )


            # for each annotation registered for the ping set the correct value for each category
            # between mask_depth_upper and mask_depth_lower
            for row in rows:
                up = float(str(row['mask_depth_upper'])) - ( float(raw_heave[pingnum])+float(raw_transducer[0][pingnum]) )
                lo = float(str(row['mask_depth_lower'])) - ( float(raw_heave[pingnum])+float(raw_transducer[0][pingnum]) )
                #print(str(len(rawpinglist))+" "+str(pingnum)+"  "+str(up)+" "+str(lo) +" "+str(raw_heave[pingnum])+" "+str(raw_transducer[0][pingnum]))
                scale = (float(len(data_range)) / 500.0)
                up2 = up * scale
                lo2 = lo * scale
                #rangepos = int(up2 - 5)
                #end=int(lo2 + 5)
                if np.isnan(up2):
                    up2 = np.nan_to_num(up2)
                if np.isnan(lo2):
                    lo2 = np.nan_to_num(lo2)
                startpos = int(up2)
                endpos = int(lo2)
                if endpos >= len(data_range):
                    endpos = len(data_range)
                if startpos < 0 :
                    startpos = 0
                size = endpos - startpos
                if(size<1):
                    temp1 = endpos
                    endpos = startpos
                    startpos = temp1
                    if endpos >= len(data_range):
                        endpos = len(data_range)
                    if startpos < 0 :
                        startpos = 0
                    size = endpos - startpos
                #print(str(p3))
                #print(" .. .. "+row['object_id']+" : " + str(startpos) +" " + str(endpos))
                objectmodified=0
                objectsettings=allobject[row['object_id']]
                if objectsettings[11]>startpos:
                    objectsettings[11]=startpos
                    objectmodified=1
                if objectsettings[12]<endpos:
                    objectsettings[12]=endpos
                    objectmodified=1

                #print (str(p3)+" "+str(objectsettings[4])+" "+str(objectsettings[5]))
                if str(objectsettings[5]) == str(p3):
                    objectsettings[7]=start+pingnum
                    objectmodified=1
                if str(objectsettings[6]) == str(p3):
                    objectsettings[8]=start+pingnum
                    objectmodified=1

                if objectmodified==1:
                    allobject[row['object_id']]=objectsettings
                    #print(" ..K .. "+row['object_id']+" : " + str(objectsettings[4]) +" " + str(objectsettings[5]))
                
                lsssupperthr_tmp [pingnum ] = float(str(row['upperThreshold']))
                lssslowerthr_tmp [pingnum ] = float(str(row['lowerThreshold']))
                
                if pingnum > -1:
                    ct = 0;
                    # write the annotation for the correct category
                    for ctg in category:
                        lsss_tmp[ct, pingnum, startpos:endpos] = 0.0
                        if str(row['acoustic_category']) == str(ctg):
                            propval= float(row['proportion'])
                            lsss_tmp[ct, pingnum, startpos:endpos] = np.full((size),propval)
                            #print(str(p3)+"  "+str(propval) +"  "+ str(ctg) )
                        ct = ct + 1
                    # get the unique number for each object_id
                    o1=shipID + "__" + str(row['object_id'])
                    #if o1 in objectnum :
                    #    objn=objectnum[o1]
                    #else:
                    #    objectnumcounter=objectnumcounter+1
                    #    objn=objectnumcounter
                    #    objectnum[o1]=objn
                    #objn = objectsettings[1]

                    objn = objectsettings[1]

                    # set the object number in lsssobject
                    lsssobject_tmp[pingnum,startpos:endpos] = objn
                    lsssobjecttype_tmp[pingnum,startpos:endpos] = type

                    # Set the exclude masks for all categories
                    if type == 0 :
                        ct = 0;
                        for ctg in category:
                            lsss_tmp[ct, pingnum, startpos:endpos] = np.nan
                            ct = ct + 1
                        lsssobject_tmp[pingnum, startpos:endpos] = -1
                        lsssobjecttype_tmp[pingnum, startpos:endpos] = type


            #now = time.time()
            #print(len(rows))
            #print("time : {0} seconds  ".format(now - program_starts))
            type = type - 1
        pingnum = pingnum + 1
    print("dask")
    lsssupperthr_dask = dask.from_array(lsssupperthr_tmp ,chunks=(-1 ))
    lssslowerthr_dask = dask.from_array(lssslowerthr_tmp ,chunks=(-1 ))
 
    lsss_dask = dask.from_array(lsss_tmp, chunks=(-1,-1,15))
    print("xarray")
    lsss = xr.DataArray(name="lsss", data=lsss_dask,
                        dims=['category','ping_time', 'range'],
                        coords={'category': category,'ping_time': data_ping, 'range': data_range})
    lsssobject_dask = dask.from_array(lsssobject_tmp, chunks=(-1,15))
    lsssobjecttype_dask = dask.from_array(lsssobjecttype_tmp, chunks=(-1,15))
    
    lsssobject = xr.DataArray(name="lsssobject", data=lsssobject_dask, dims=['ping_time', 'range'],
                    coords={'ping_time': data_ping, 'range': data_range})
    lsssobjecttype = xr.DataArray(name="lsssobjecttype", data=lsssobjecttype_dask, dims=['ping_time', 'range'],
                    coords={'ping_time': data_ping, 'range': data_range})
    lsssupperthr = xr.DataArray(name="lsssupperthr", data=lsssupperthr_dask, dims=['ping_time'],
                    coords={'ping_time': data_ping })
    lssslowerthr = xr.DataArray(name="lssslowerthr", data=lssslowerthr_dask, dims=['ping_time'],
                    coords={'ping_time': data_ping })
    print("dataset")
    ds4 = xr.Dataset(
        data_vars=dict(
            annotation=(["category","ping_time", "range"], lsss),
            object=(["ping_time", "range"], lsssobject),
            objecttype=(["ping_time", "range"], lsssobjecttype),
            upperthr=(["ping_time" ], lsssupperthr),
            lowerthr=(["ping_time" ], lssslowerthr),
        ),
        coords=dict(
            category=category,
            ping_time=data_ping,
            range=data_range,
        )
    )
    git_rev = os.getenv('COMMIT_SHA', 'XXXXXXXX')
    try:
        git_rev =  subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()

    except Exception as e:
        print("error getting git revision")
    # Append version attributes
    ds4.attrs = dict(
        name = "CRIMAC-labels",
        description="CRIMAC-labels",
        time = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        commit_sha = git_rev
    )
    ds4 = ds4.chunk({"category": 1, "range": ds4.range.shape[0], "ping_time": pingchunk})
    compressor = Blosc(cname='zstd', clevel=3, shuffle=Blosc.BITSHUFFLE)
    encoding = {var: {"compressor": compressor} for var in ds4.data_vars}

    print("write start")
    if writemode==0:
        # first write to a new file
        ds4.to_zarr(savefile, mode="w", encoding=encoding)
    else:
        # append
        ds4.to_zarr(savefile, mode="a",   append_dim="ping_time")
    print("write end")
    print ("pingerror: "+str(pingerror))
    print ("pingok: " +str(pingok ))


# open raw data zarr to get the dimensions
z = xr.open_zarr(rawfile, chunks={'ping_time':'50000'})

totalpings = z.sv.shape[1]
rangechunk = z.sv.shape[2]

fc2 = open(parquetfile2+"pings.csv", 'w')


data11 = z.sv.isel(frequency=slice(0, 1), ping_time=slice(0, totalpings), range=slice(0, rangechunk))
    #array with pingtime
data_ping11 = np.asarray(data11.ping_time )

d6=[]
for pingx in data_ping11 :
    p6 =pingx
    if str(pingx).endswith("9")  :
        p6 =pingx +np.timedelta64(1, 'ns')
        print(type(pingx))
        print(str(p6)+" "+ str(pingx))
    if str(pingx).endswith("8")  :
        p6 =pingx +np.timedelta64(2, 'ns')
        print(type(pingx))
        print(str(p6)+" "+ str(pingx))
    if str(pingx).endswith("7")  :
        p6 =pingx +np.timedelta64(3, 'ns')
        print(type(pingx))
        print(str(p6)+" "+ str(pingx))
    fc2.write(str(p6))
    fc2.write('\n')
fc2.close()



print(totalpings)
print(rangechunk)

# open parquet file with annotations
table1 = pq.read_table( parquetfile2)
t1 = table1.to_pandas()
print("___")

allobject = {}

# Dictionaries to store annotation based on priority
work3 = {}
work2 = {}
work1 = {}
workexclude = {}

workannot=[]
workannot.append(work3)
workannot.append(work2)
workannot.append(work1)
workannot.append(workexclude)

acoustic_category = {}
print(t1)
lastobject="emptyid"
objectcount=0
firstrow = {}
lastrow = {}
obj_cat = {}

pcount=0


fc2 = open(parquetfile2+"test.csv", 'w')
writercsv2 = csv.writer(fc2)



#fc = open(parquetfile2+".csv", 'w')
#writercsv = csv.writer(fc)

for index, row in t1.iterrows():
    pcount=pcount+1

    objectid=row['object_id']
    if objectid!=lastobject:
        lastobject=objectid
        objectcount=objectcount+1
        row['object_id'] = str(objectcount)+"__"+objectid
        if objectcount >1:
            row2=[]
            row2.append(firstrow['object_id'])
            idarray=firstrow['object_id'].split("__")
            id2=idarray[1].split("-")
            #row2.append(idarray[0])
            if len(id2)<2:
                row2.append(0)
            elif id2[1] == 'None':
                row2.append(0)
            elif len(id2)>1:
                row2.append(id2[1])
            else:
                row2.append(10000+int(idarray[0]))
            row2.append(idarray[1])
            row2.append(firstrow['acoustic_category'])
            row2.append(firstrow['proportion'])
            if(lastrow['ping_time']>firstrow['ping_time']):
                row2.append(firstrow['ping_time'])
                row2.append(lastrow['ping_time'])
            else:
                row2.append(lastrow['ping_time'])
                row2.append(firstrow['ping_time'])
            row2.append(100000000)
            row2.append(0)
            row2.append(firstrow['mask_depth_upper'])
            row2.append(firstrow['mask_depth_lower'])
            row2.append(100000000)
            row2.append(0)
            row2.append(obj_cat)

            allobject[firstrow['object_id']]=row2
            print("  __  "+ firstrow['object_id'])
            #writercsv.writerow(row2)
            #if int(float(lastrow['acoustic_category']))==12:
            #test1=[ "@", lastrow['object_id'],lastrow['ping_time'],lastrow['acoustic_category'],lastrow['proportion'],obj_cat]
            #writercsv2.writerow( test1)

            #print(test1)
            obj_cat.clear()
            print(obj_cat)
        firstrow=row
    c1 = int(float(row['acoustic_category']))
    pr = float(row['proportion'])
    obj_cat[c1] = pr
    # print(str(row['ping_time'])+" "+row['object_id']+" "+str(c1)+" "+str(pr))
    #test1 = [objectcount, row['object_id'], row['ping_time'], row['acoustic_category'], row['proportion'], obj_cat]
    #writercsv2.writerow(test1)
    p1 = int(row['priority'])
    #Sif objectcount >1:
        #test1=[ "0", lastrow['object_id'],lastrow['ping_time'],lastrow['acoustic_category'],lastrow['proportion']]
        #writercsv2.writerow( test1)
    lastrow = row
    row['object_id'] = str(objectcount)+"__"+objectid


    #put all annotations in a list and save the list in the dictionary for each pingtime key
    if c1 > 0 or c1 == -1:
        if str(row['ping_time'])[0:26] in workannot[3-p1]:
            workannot[3-p1][str(row['ping_time'])[0:26]].append(row)
        else:
            annotlist = []
            annotlist.append(row)
            workannot[3-p1][str(row['ping_time'])[0:26]] = annotlist
        acoustic_category[str(row['acoustic_category'])] = str(row['priority'])
    else:
        # save exclude annotation in its own dictionary  , pingtime key
        if str(row['ping_time'])[0:26] in workannot[3]:
            workannot[3][str(row['ping_time'])[0:26]].append(row)
        else:
            annotlist = []
            annotlist.append(row)
            workannot[3][str(row['ping_time'])[0:26]] = annotlist

    if pcount%500000 ==0:
        print("  annotation pings "+str(len(workannot[0])) +" "+str(len(workannot[1])) +" "+str(len(workannot[2])) +" "+str(len(workannot[3])))

row2=[]
row2.append(firstrow['object_id'])
idarray=firstrow['object_id'].split("__")
id2=idarray[1].split("-")
#row2.append(idarray[0])
if len(id2)<2:
    row2.append(0)
elif id2[1] == 'None': 
    row2.append(0)
elif len(id2)>1: 
    row2.append(id2[1])
else:
    row2.append(10000+int(idarray[0]))
row2.append(idarray[1])
row2.append(firstrow['acoustic_category'])
row2.append(firstrow['proportion'])
if(lastrow['ping_time']>firstrow['ping_time']):
    row2.append(firstrow['ping_time'])
    row2.append(lastrow['ping_time'])
else:
    row2.append(lastrow['ping_time'])
    row2.append(firstrow['ping_time'])
row2.append(100000000)
row2.append(0)
row2.append(firstrow['mask_depth_upper'])
row2.append(firstrow['mask_depth_lower'])
row2.append(100000000)
row2.append(0)
row2.append(obj_cat)

fc2.close()


allobject[firstrow['object_id']]=row2
print("  __  "+ firstrow['object_id'])

category=[]
# we want to save each category as an int value
for key1 in acoustic_category:
    cat2= int(float(key1))
    if cat2 in category:
        print ("duplicate category "+str (cat2))
    else:
        category.append(cat2)
print(category)
print(acoustic_category)




numberofreads = math.ceil(totalpings / pingchunk)
print(numberofreads)
i = 0
print("remaining annotation pings " + str(len(workannot[0])) + " " + str(len(workannot[1])) + " " + str( len(workannot[2])) + " " + str(len(workannot[3])))

#Loop though all pings in the raw file in chunks and save the annotation
while( i < totalpings):

    print(str(i)+" "+ str(i+pingchunk))

    if i==0:
        # first write
        print(str(i) + " 1 " + str(i + pingchunk))
        write_annot(rawfile, allobject, i, (i + pingchunk),rangechunk, savefile2, 0)
    else:
        # append to file
        print(str(i) + " x " + str(i + pingchunk))
        write_annot(rawfile,allobject, i, (i + pingchunk),rangechunk, savefile2, 1)
    i += pingchunk
    print("remaining annotation pings "+str(len(workannot[0])) +" "+str(len(workannot[1])) +" "+str(len(workannot[2])) +" "+str(len(workannot[3])))

print("---")
for v in workannot[0]:
   print(v)
print("---")
for v in workannot[1]:
   print(v)
print("---")
for v in workannot[2]:
   print(v)
print("---")
for v in workannot[3]:
   print(v)


fc = open(parquetfile2+".csv", 'w')
writercsv = csv.writer(fc)
csvheader =[
"ID",
"object",
"type",
"category",
"proportion",
"startping",
"endping",
"startpingindex",
"endpingindex",
"upperdepth",
"lowerdepth",
"upperdepthindex",
"lowerdepthindex",
"category-proportion"
]
writercsv.writerow(csvheader)
for ob in allobject:
    print(ob)
    print(allobject[ob])
    writercsv.writerow(allobject[ob])
fc.close()




zarr.consolidate_metadata(savefile2 )
z2 = xr.open_zarr(savefile2 )
print(z2)