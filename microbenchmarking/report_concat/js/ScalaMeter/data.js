var ScalaMeter = (function(parent) {
  var my = { name: "data" };
  my.index = [{"scope" : ["List", "concatenation"], "name" : "Test-0", "unit" : "", "file" : "..\/List.concatenation.Test-0.dsv"}, {"scope" : ["List", "builder +="], "name" : "Test-1", "unit" : "", "file" : "..\/List.builder +=.Test-1.dsv"}, {"scope" : ["List", "builder ++="], "name" : "Test-2", "unit" : "", "file" : "..\/List.builder ++=.Test-2.dsv"}, {"scope" : ["String", "concatenation"], "name" : "Test-3", "unit" : "", "file" : "..\/String.concatenation.Test-3.dsv"}, {"scope" : ["String", "builder +="], "name" : "Test-4", "unit" : "", "file" : "..\/String.builder +=.Test-4.dsv"}, {"scope" : ["String", "builder ++="], "name" : "Test-5", "unit" : "", "file" : "..\/String.builder ++=.Test-5.dsv"}, {"scope" : ["Set", "concatenation"], "name" : "Test-6", "unit" : "", "file" : "..\/Set.concatenation.Test-6.dsv"}, {"scope" : ["Set", "builder +="], "name" : "Test-7", "unit" : "", "file" : "..\/Set.builder +=.Test-7.dsv"}, {"scope" : ["Set", "builder ++="], "name" : "Test-8", "unit" : "", "file" : "..\/Set.builder ++=.Test-8.dsv"}, {"scope" : ["Array", "copy"], "name" : "Test-9", "unit" : "", "file" : "..\/Array.copy.Test-9.dsv"}, {"scope" : ["Array", "builder +="], "name" : "Test-10", "unit" : "", "file" : "..\/Array.builder +=.Test-10.dsv"}, {"scope" : ["Array", "builder ++="], "name" : "Test-11", "unit" : "", "file" : "..\/Array.builder ++=.Test-11.dsv"}];
  my.tsvData = ['date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:02:27Z	10000	0.1938831666666667	true	0.165	0.223	ms	"0.180749 0.181991 0.183025 0.184007 0.185093 0.19672 0.231137 0.240196 0.176929 0.177937 0.178154 0.179649 0.180485 0.182103 0.185506 0.18835 0.181417 0.182033 0.182857 0.183747 0.177733 0.177959 0.180563 0.183674 0.231139 0.24216 0.272388 0.284301 0.177538 0.178711 0.184579 0.186106 0.183263 0.183863 0.185532 0.1882"\n2018-03-20T11:16:08Z	1000	0.15670219444444441	true	0.047	0.267	ms	"0.146473 0.209893 0.275672 0.488718 0.061704 0.062372 0.066098 0.066401 0.232588 0.238955 0.239407 0.353029 0.235857 0.240523 0.240709 0.250855 0.060837 0.061575 0.06239 0.062774 0.220412 0.226532 0.229375 0.236604 0.070553 0.096687 0.101805 0.109261 0.062351 0.064766 0.101101 0.103673 0.061472 0.09875 0.098852 0.102255"\n2018-03-20T13:27:59Z	10000	0.27102163888888886	true	0.176	0.366	ms	"0.193373 0.332737 0.345292 0.351512 0.184236 0.186249 0.202743 0.205144 0.336727 0.357875 0.377634 0.537606 0.182038 0.269716 0.332409 0.417352 0.19078 0.193131 0.193351 0.196215 0.299229 0.308342 0.315891 0.33498 0.190215 0.191224 0.192797 0.194296 0.191692 0.238218 0.348069 0.349309 0.181681 0.182697 0.3114 0.340619"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:02:27Z	10000	0.17743308333333332	true	-0.001	0.356	ms	"0.106276 0.108425 0.108588 0.111336 0.106252 0.107064 0.108637 0.111476 0.11269 0.123678 0.182608 0.257412 0.10729 0.107612 0.110508 0.111334 0.109401 0.112232 0.115375 0.115929 0.122884 0.123338 0.124938 0.125281 0.108338 0.108513 0.109991 0.111636 0.108429 0.12194 0.132504 0.164381 0.513862 0.536585 0.705858 0.73499"\n2018-03-20T11:16:08Z	1000	0.08531611111111113	true	0.058	0.113	ms	"0.057321 0.057836 0.058011 0.058537 0.08846 0.089445 0.093102 0.096752 0.06202 0.129368 0.13465 0.173413 0.09419 0.095411 0.099806 0.107981 0.090591 0.090856 0.091495 0.092391 0.057042 0.057633 0.060127 0.062584 0.057138 0.057334 0.059381 0.061854 0.087135 0.090881 0.091092 0.097387 0.090165 0.091105 0.0928 0.096086"\n2018-03-20T13:27:59Z	10000	0.3046752222222222	true	0.117	0.492	ms	"0.688032 0.69747 0.730665 0.876403 0.219524 0.220057 0.220231 0.221203 0.211764 0.213964 0.234492 0.253946 0.2199 0.219928 0.221977 0.222173 0.211362 0.212966 0.21494 0.216015 0.208812 0.210361 0.211494 0.213336 0.214967 0.217614 0.33652 0.357284 0.357634 0.379482 0.421589 0.459785 0.212333 0.21304 0.213163 0.213882"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:08:16Z	10000	0.1437369166666667	true	0.080	0.207	ms	"0.09195 0.092902 0.095626 0.096892 0.151716 0.153215 0.155039 0.155429 0.085218 0.088897 0.14658 0.18346 0.084851 0.0873 0.108617 0.146755 0.19308 0.274968 0.307509 0.350366 0.128283 0.129248 0.129956 0.130874 0.131579 0.135872 0.137362 0.137585 0.143345 0.144504 0.150238 0.150985 0.089907 0.103819 0.133062 0.14754"\n2018-03-20T11:16:08Z	1000	0.060081166666666665	true	0.048	0.072	ms	"0.05323 0.055676 0.056426 0.060308 0.053372 0.055796 0.056 0.057069 0.055322 0.05596 0.059755 0.059925 0.053806 0.055054 0.056742 0.058398 0.053663 0.055133 0.056708 0.058226 0.053242 0.053467 0.053474 0.054216 0.086734 0.087416 0.091425 0.092582 0.058981 0.060233 0.060476 0.060788 0.054675 0.055373 0.056445 0.056826"\n2018-03-20T13:27:59Z	10000	0.12282433333333333	true	0.088	0.158	ms	"0.089477 0.089919 0.091293 0.093523 0.132838 0.136021 0.139167 0.139197 0.088554 0.089044 0.089223 0.090088 0.146011 0.147703 0.153006 0.165529 0.094743 0.129887 0.150895 0.241633 0.132951 0.134562 0.137558 0.142452 0.138934 0.139882 0.140969 0.150822 0.090139 0.091131 0.091687 0.093293 0.092083 0.102279 0.115375 0.129808"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:08:16Z	10000	40.473922972222226	true	30.809	50.139	ms	"34.783981 35.307748 37.797562 40.828539 34.325527 36.173439 36.595141 42.210667 34.175072 37.015275 37.624931 41.858253 34.909475 37.2799 60.800854 76.895462 49.213659 49.822937 53.465374 53.682374 33.470111 33.727512 33.93485 34.020589 35.711151 36.539691 39.579636 43.44621 35.092877 36.467357 37.968736 41.064969 35.067666 36.880531 38.614553 40.708618"\n2018-03-20T11:16:08Z	1000	0.2814950555555556	true	0.219	0.344	ms	"0.231544 0.232024 0.238179 0.239613 0.250704 0.253196 0.255232 0.256451 0.248113 0.249046 0.250015 0.251026 0.292223 0.296382 0.398155 0.475052 0.249948 0.256171 0.306485 0.317905 0.234426 0.242001 0.246016 0.248658 0.296731 0.304867 0.305728 0.306984 0.251381 0.252738 0.253348 0.253766 0.26472 0.333981 0.338643 0.45237"\n2018-03-20T13:27:59Z	10000	34.485248194444445	true	33.076	35.894	ms	"33.943308 34.031068 34.064714 34.404356 32.142063 33.849377 34.811742 36.032317 33.604235 34.528325 35.219481 36.442488 32.35044 34.193689 34.711586 35.19214 33.635825 33.850241 34.030413 34.375649 32.925753 34.322877 34.336194 34.855242 32.933029 33.99762 34.050116 34.225356 32.781988 34.25942 34.830155 35.103212 34.684913 36.788409 37.605279 38.355915"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:08:16Z	10000	0.7006753055555555	true	-0.541	1.942	ms	"0.240341 0.246335 0.289015 0.322819 0.244535 0.273444 0.297921 0.362256 0.242883 0.248013 0.282265 0.293856 0.433332 0.474721 0.548114 0.699028 0.51221 1.153013 4.856259 5.74391 0.525959 0.582379 0.691728 0.758993 0.242908 0.260595 0.294413 0.312321 0.408901 0.409204 0.476909 0.51366 0.441948 0.455652 0.521451 0.56302"\n2018-03-20T11:16:08Z	1000	0.10409311111111112	true	0.052	0.156	ms	"0.211198 0.211631 0.215689 0.273649 0.070654 0.075582 0.103656 0.110388 0.070361 0.071919 0.080859 0.086061 0.078732 0.080927 0.091227 0.095861 0.121819 0.122477 0.127099 0.128434 0.065833 0.06863 0.076715 0.079506 0.081345 0.092849 0.104762 0.112674 0.07704 0.07733 0.089069 0.094463 0.069761 0.072151 0.076178 0.080823"\n2018-03-20T13:27:59Z	10000	0.46059300000000003	true	0.251	0.670	ms	"0.252864 0.605536 0.69834 1.343059 0.239943 0.316843 0.375956 0.399965 0.429093 0.458213 0.486861 0.505817 0.239962 0.245373 0.619859 0.624311 0.295828 0.439686 0.504649 0.51101 0.432819 0.452712 0.514772 0.550737 0.445872 0.446388 0.451362 0.530559 0.243522 0.25024 0.543362 0.573821 0.286654 0.398878 0.42438 0.442102"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:08:16Z	10000	0.3924636666666667	true	0.227	0.558	ms	"0.235797 0.258484 0.280147 0.299797 0.409761 0.42902 0.434238 0.448748 0.238593 0.503462 0.568827 0.963264 0.312165 0.388954 0.402077 0.402826 0.312715 0.341319 0.343095 0.365675 0.336706 0.345545 0.403355 0.451047 0.220014 0.267198 0.383794 0.63934 0.219917 0.224037 0.41643 0.791808 0.309585 0.342953 0.400443 0.437556"\n2018-03-20T11:16:08Z	1000	0.11631422222222224	true	0.077	0.156	ms	"0.103609 0.104792 0.108008 0.112145 0.131982 0.13295 0.135514 0.156198 0.074304 0.074993 0.077391 0.080913 0.070754 0.075789 0.077882 0.077932 0.115203 0.117696 0.118358 0.122145 0.071583 0.074371 0.076751 0.077023 0.11483 0.11606 0.120916 0.124504 0.164684 0.166183 0.188403 0.190637 0.129878 0.163634 0.168509 0.170788"\n2018-03-20T13:27:59Z	10000	0.3679670833333333	true	0.225	0.511	ms	"0.343147 0.424892 0.598612 0.712236 0.341246 0.599688 0.626689 0.64868 0.21827 0.229345 0.273045 0.357807 0.329198 0.378487 0.380197 0.426683 0.218114 0.230923 0.251671 0.272262 0.220407 0.279393 0.342833 0.346661 0.333516 0.381893 0.423474 0.49509 0.226694 0.232817 0.260167 0.286124 0.342057 0.351611 0.416473 0.446413"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:16:08Z	1000	22.808175805555553	true	18.758	26.859	ms	"21.36751 21.99657 23.890955 26.482464 19.63967 21.057784 28.863925 31.370867 18.223712 19.06697 23.477088 24.68213 19.359626 24.75953 26.877792 30.419437 19.534914 19.816287 21.136998 21.66444 20.03833 22.259325 25.402304 26.130414 20.015457 23.328029 27.122073 31.551342 20.057197 21.187531 22.020476 22.428748 18.004676 18.627387 19.412737 19.819634"\n2018-03-20T13:27:59Z	10000	4609.994662583334	true	4409.596	4810.393	ms	"4420.652367 4494.07529 4693.044332 4787.34158 4278.919599 4310.672301 4470.90824 4671.20074 4389.412235 4523.915436 4740.447204 4832.808812 4403.107593 4554.008368 4672.036821 4837.88218 4308.118622 4433.518219 4646.094675 4759.178832 4433.008938 4491.912352 4592.525605 4764.398294 4589.740485 4598.237651 4814.111064 5012.080003 4532.757151 4598.059266 4834.133044 4956.967776 4499.505033 4506.644022 4667.00375 4841.379973"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:16:08Z	1000	0.4830104166666668	true	-0.178	1.144	ms	"0.202178 0.215186 0.217422 0.219077 0.191314 0.21021 0.213692 0.21495 0.286781 0.30968 0.311047 0.347601 0.242215 0.36869 0.375185 0.409386 0.19892 0.300275 0.346222 0.355401 1.278939 1.59268 2.137646 3.158514 0.298847 0.301771 0.306759 0.312376 0.200713 0.200794 0.22096 0.236298 0.340221 0.398787 0.409818 0.45782"\n2018-03-20T13:27:59Z	10000	0.7029514166666667	true	0.566	0.840	ms	"0.551088 0.561401 0.566753 0.576558 0.803832 0.813485 0.814731 0.815455 0.795144 0.798747 0.818293 0.819241 0.809167 0.810329 0.81428 0.8455 0.563913 0.566052 0.570887 0.579593 0.700006 0.817647 0.842694 0.858625 0.807252 0.824302 0.825088 0.827019 0.555269 0.556221 0.558863 0.560898 0.565546 0.570463 0.570502 0.571407"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:16:08Z	1000	0.18641758333333333	true	0.092	0.281	ms	"0.103805 0.10555 0.10851 0.113506 0.290353 0.296598 0.337018 0.338388 0.102112 0.10227 0.1095 0.115037 0.133523 0.180598 0.205044 0.250084 0.167828 0.169672 0.173714 0.190935 0.102554 0.103345 0.112365 0.121887 0.326503 0.331505 0.331662 0.333675 0.194092 0.208868 0.253537 0.260555 0.104837 0.108378 0.110782 0.112443"\n2018-03-20T13:27:59Z	10000	1.5088966944444444	true	1.359	1.659	ms	"1.411268 1.411658 1.856447 2.064313 1.431158 1.487172 1.497196 1.555253 1.449143 1.477622 1.614102 1.709018 1.399652 1.408481 1.411428 1.424077 1.403095 1.453486 1.644447 1.677512 1.48888 1.500006 1.525789 1.56477 1.406144 1.409195 1.418093 1.420943 1.446308 1.483576 1.486729 1.521302 1.404466 1.42227 1.513196 1.522086"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:16:08Z	1000	0.0035249444444444447	true	0.001	0.006	ms	"0.002851 0.003051 0.003128 0.003548 0.002258 0.002412 0.002497 0.002764 0.002064 0.002184 0.002248 0.002642 0.001868 0.001969 0.002325 0.003578 0.001935 0.002816 0.003395 0.00543 0.002007 0.002072 0.0029 0.003906 0.002892 0.003038 0.004064 0.006084 0.006958 0.007061 0.008557 0.009732 0.001986 0.003069 0.003119 0.00449"\n2018-03-20T13:27:59Z	10000	0.010388999999999999	true	0.008	0.013	ms	"0.006886 0.007199 0.007977 0.00875 0.011565 0.012546 0.013933 0.013947 0.009802 0.01156 0.011575 0.012114 0.00683 0.007236 0.007982 0.009546 0.011696 0.011744 0.01252 0.013677 0.00677 0.007411 0.007844 0.009207 0.010658 0.011198 0.012887 0.014744 0.006846 0.007954 0.008021 0.009186 0.012084 0.01271 0.01309 0.014309"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:16:08Z	1000	0.06886497222222222	true	0.050	0.088	ms	"0.047849 0.048399 0.052162 0.056532 0.055862 0.05632 0.058455 0.061076 0.045747 0.046814 0.050547 0.057297 0.054514 0.057545 0.057679 0.058731 0.090248 0.095355 0.095476 0.099077 0.078605 0.083658 0.084615 0.087788 0.050526 0.051432 0.053235 0.055329 0.086706 0.08887 0.089742 0.092975 0.078713 0.079101 0.084186 0.087973"\n2018-03-20T13:27:59Z	10000	0.2534298611111111	true	0.087	0.420	ms	"0.114389 0.114638 0.182654 0.19146 0.398318 0.439178 0.445698 0.450877 0.121245 0.121772 0.128406 0.128777 0.116053 0.117831 0.122451 0.123195 0.273883 0.27942 0.279573 0.289805 0.182199 0.183293 0.184176 0.187752 0.537468 0.539349 0.559286 0.582755 0.114195 0.11477 0.11851 0.119384 0.199398 0.291262 0.293426 0.476629"\n', 'date	param-size	value	success	cilo	cihi	units	complete\n2018-03-20T11:16:08Z	1000	0.08023102777777778	true	0.050	0.111	ms	"0.053972 0.055622 0.059763 0.06318 0.054447 0.055781 0.060345 0.060852 0.054222 0.055014 0.063086 0.068495 0.132975 0.143032 0.14344 0.16201 0.079118 0.083558 0.085126 0.094771 0.088302 0.089225 0.096979 0.098917 0.064268 0.087737 0.088135 0.096104 0.048245 0.048533 0.05438 0.057172 0.079449 0.082835 0.086966 0.092261"\n2018-03-20T13:27:59Z	10000	0.14086219444444442	true	0.041	0.241	ms	"0.089856 0.090767 0.093183 0.097204 0.089961 0.092599 0.110421 0.117814 0.090088 0.091155 0.092397 0.095038 0.091214 0.092351 0.098162 0.103195 0.13477 0.141825 0.146688 0.169618 0.093995 0.097803 0.099891 0.100424 0.279815 0.382371 0.402221 0.467671 0.153536 0.154478 0.154901 0.164859 0.089122 0.090801 0.10109 0.109755"\n'];
  parent[my.name] = my;
  return parent;
})(ScalaMeter || {});