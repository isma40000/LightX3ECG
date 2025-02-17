
import os, sys
from libs import *
from utils import *
import neurokit2 as nk
import configVars


def train_fn(
    train_loaders, 
    model, 
    num_epochs, 
    config, 
    criterion, 
    optimizer, 
    scheduler = None, 
    save_ckp_dir = "./", 
    training_verbose = True, 
):
    print("\nStart Training ...\n" + " = "*16)
    model = model.cuda()
    model = nn.DataParallel(model, device_ids = config["device_ids"])

    best_f1 = 0.0
    best_prec = 0.0
    best_recall = 0.0
    
    for epoch in tqdm(range(1, num_epochs + 1), disable = training_verbose):
        if training_verbose:print("epoch {:2}/{:2}".format(epoch, num_epochs) + "\n" + "-"*16)

        model.train()
        running_loss = 0.0
        running_labels, running_preds = [], []
        for ecgs, labels in tqdm(train_loaders["train"], disable = not training_verbose):
            ecgs, labels = ecgs.cuda(), labels.cuda()

            logits = model(ecgs)
            loss = criterion(logits, labels) #input,target

            loss.backward()
            optimizer.step(), optimizer.zero_grad()

            running_loss = running_loss + loss.item()*ecgs.size(0)
            labels, preds = list(labels.data.cpu().numpy()), list(torch.max(logits, 1)[1].detach().cpu().numpy()) if not config["is_multilabel"] else list(np.where(torch.sigmoid(logits).detach().cpu().numpy() >= 0.50, 1, 0))
            running_labels.extend(labels), running_preds.extend(preds)


        if (scheduler is not None) and (not epoch > scheduler.T_max):
            scheduler.step()
        # Cambiado para que devuelva también precisión y recall    
        epoch_loss = running_loss/len(train_loaders["train"].dataset),
        epoch_prec, epoch_recall, epoch_f1, _ = precision_recall_fscore_support(
            running_labels, running_preds
            , average = None
        )
        # if training_verbose:
        #     print("{:<5} - loss:{:.4f}, f1:{:.4f}".format(
        #         "train", 
        #         np.mean(epoch_loss), np.mean(epoch_f1)
        #     ))
        
        # print("#################################################################")
        # print(f"Forma de las running_labels: {np.array(running_labels).shape}\n")
        # print(running_labels)
        # print(f"\nForma de las running_preds: {np.array(running_preds).shape}\n")
        # print(running_preds)
        # print("#################################################################")
        
        with torch.no_grad():
            model.eval()
            running_loss = 0.0
            running_labels, running_preds = [], []
            for ecgs, labels in tqdm(train_loaders["val"], disable = not training_verbose):
                ecgs, labels = ecgs.cuda(), labels.cuda()

                logits = model(ecgs)
                loss = criterion(logits, labels)

                running_loss = running_loss + loss.item()*ecgs.size(0)
                labels, preds = list(labels.data.cpu().numpy()), list(torch.max(logits, 1)[1].detach().cpu().numpy()) if not config["is_multilabel"] else list(np.where(torch.sigmoid(logits).detach().cpu().numpy() >= 0.50, 1, 0))
                running_labels.extend(labels), running_preds.extend(preds)
            # print("#################################################################")
            # print(f"Forma de las running_labels: {np.array(running_labels).shape}\n")
            # print(running_labels)
            # print(f"\nForma de las running_preds: {np.array(running_preds).shape}\n")
            # print(running_preds)
            # print("#################################################################")
        # Cambiado para que devuelva también precisión y recall        
        epoch_loss = running_loss/len(train_loaders["val"].dataset)
        epoch_prec, epoch_recall, epoch_f1, _ = precision_recall_fscore_support(
            running_labels, running_preds
            , average = None
        )
        # if training_verbose:
        #     print("{:<5} - loss:{:.4f}, f1:{:.4f}".format(
        #         "val", 
        #         np.mean(epoch_loss), np.mean(epoch_f1)
        #     ))
        if np.mean(epoch_f1) > np.mean(best_f1):
            best_f1 = epoch_f1; 
            best_prec = epoch_prec; 
            best_recall = epoch_recall; 
            torch.save(model.module, f"{save_ckp_dir}/best.ptl")

    #En esta evaluación se está prediciendo realmente
    print("\nStart Evaluation ...\n" + " = "*16)
    model = torch.load(f"{save_ckp_dir}/best.ptl", map_location = "cuda")
    model = nn.DataParallel(model, device_ids = config["device_ids"])

    with torch.no_grad():
        model.eval()
        running_labels, running_preds = [], []
        for ecgs, labels in tqdm(train_loaders["val"], disable = not training_verbose):
            ecgs, labels = ecgs.cuda(), labels.cuda()

            logits = model(ecgs)

            #labels son las etiquetas reales y preds las que ha predicho el modelo
            labels, preds = list(labels.data.cpu().numpy()), list(torch.max(logits, 1)[1].detach().cpu().numpy()) if not config["is_multilabel"] else list(torch.sigmoid(logits).detach().cpu().numpy())
            running_labels.extend(labels), running_preds.extend(preds)
            
        # print("#################################################################")
        # print(f"Forma de las running_labels: {np.array(running_labels).shape}\n")
        # print(running_labels)
        # print(f"\nForma de las running_preds: {np.array(running_preds).shape}\n")
        # print(running_preds) 
        # print("#################################################################")
    
    if config["is_multilabel"]:
        running_labels, running_preds = np.array(running_labels), np.array(running_preds)
        #Te quedas con los umbrales que tienen un mejor f1_score
        optimal_thresholds = thresholds_search(running_labels, running_preds)
        running_preds = np.stack([
            #Determinas si las predicciones cumplen con el umbral óptimo, los umbrales óptimos son los que tienen mejor f1_score y menor pérdida
            np.where(running_preds[:, cls] >= optimal_thresholds[cls], 1, 0) for cls in range(running_preds.shape[1])
        ]).transpose()
    val_loss = running_loss/len(train_loaders["val"].dataset)
    val_prec, val_recall, val_f1, _ = precision_recall_fscore_support(
        running_labels, running_preds
        , average = None
    )
    # print("{:<5} - loss:{:.4f}, f1:{:.4f}".format(
    #     "val", 
    #     np.mean(val_loss), np.mean(val_f1)
    # ))
    print("############Validation###########\n")
    print(f"\nPrecision:{val_prec}\n{val_prec.shape}\nRecall:{val_recall}\n{val_recall.shape}\nF1:{val_f1}\n{val_f1.shape}\n")
    print(np.array([val_prec,val_recall,val_f1]))
    # df = pandas.DataFrame(
    #     [{
    #         'Precision': val_prec,
    #         'Recall': val_recall,
    #         'F1': val_f1 
    #     }],
    #     index=["Normal","AF","I-AVB","LBBB","RBBB","PAC","PVC","STD","STE"]
    # )
    # df["Precision"],df["Recall"],df["F1"] = val_prec,val_recall,val_f1
    if val_prec.shape[0] == 9:
        df = pandas.DataFrame(np.array([val_prec,val_recall,val_f1]).transpose(),columns=["Precision","Recall","F1"],index=["Normal","AF","I-AVB","LBBB","RBBB","PAC","PVC","STD","STE"])
    else:
        df = pandas.DataFrame(np.array([val_prec,val_recall,val_f1]).transpose(),columns=["Precision","Recall","F1"],index=["Label_0","Label_1","Label_2","Label_3"])
        
    df.loc['Average'] = df.mean()
    df.index.names = ['Class']
    df.to_csv("../../drive/Shareddrives/TFG_INFO/Codigo/Casos/Chapman/tabla.csv")
    
    ax = pyplot.subplot(111, frame_on=False) # no visible frame
    ax.xaxis.set_visible(False)  # hide the x axis
    ax.yaxis.set_visible(False)  # hide the y axis
    table(ax, df)  # where df is your data frame

    pyplot.savefig("../../drive/Shareddrives/TFG_INFO/Codigo/Casos/Chapman/tabla.png")
    print("#################################\n")
    
    
############################################################################################
############################################################################################
################################### BAJO CONSTRUCCIÓN ######################################
############################################################################################
############################################################################################

def get_r_count(ecg):
    counts = []
    for i in range(ecg.shape[0]):
        try:
            count = len(nk.ecg_peaks(ecg[i, :], sampling_rate=500)[1]['ECG_R_Peaks'].tolist())
        except:
            count = 0
        counts.append(count)
    return max(set(counts), key = counts.count)

############################################################################################
############################################################################################
################################### BAJO CONSTRUCCIÓN ######################################
############################################################################################
############################################################################################

def predict(
    train_loaders, 
    model, 
    config,
    save_ckp_dir = "./", 
    training_verbose = True, 
):
    model = torch.load(f"{save_ckp_dir}/best.ptl", map_location = "cuda")
    model = nn.DataParallel(model, device_ids = config["device_ids"])
    
    with torch.no_grad():
        model.eval()
        running_labels, running_preds = [], []
        for ecgs, labels in tqdm(train_loaders["pred"], disable = not training_verbose):
            #######CODIGO USADO PARA MOSTRAR EL R_COUNT DE LOS CASOS######
            # print(f"\n{ecgs[0]}:{ecgs[0].shape}")
            # i = 1
            # for ecg in ecgs:
            #     print(f"\nEl r_count del Caso {i} es: {get_r_count(ecg)}")
            #     i+=1
            ##############################################################    
            ecgs, labels = ecgs.cuda(), labels.cuda()
            logits = model(ecgs)

            #labels son las etiquetas reales y preds las que ha predicho el modelo
            labels, preds = list(labels.data.cpu().numpy()), list(torch.max(logits, 1)[1].detach().cpu().numpy()) if not config["is_multilabel"] else list(torch.sigmoid(logits).detach().cpu().numpy())
            running_labels.extend(labels), running_preds.extend(preds)
    print(f"{running_preds}")    
    if config["is_multilabel"]:
        running_labels, running_preds = np.array(running_labels), np.array(running_preds)
        #Te quedas con los umbrales que tienen un mejor f1_score
        print(f"El reshapeo del array{running_labels.shape}")
        print(f"El reshapeo del array{running_preds.shape}")
        optimal_thresholds = thresholds_search(running_labels, running_preds)
        running_probs = running_preds
        running_preds = np.stack([
            np.where(running_preds[:, cls] >= optimal_thresholds[cls], 1, 0) for cls in range(running_preds.shape[1])
        ]).transpose()
    else:   
        #########################PRUEBA########################
        running_labels, running_preds = np.array(running_labels), np.array(running_preds)
        #Te quedas con los umbrales que tienen un mejor f1_score
        running_labels=np.reshape(running_labels, (len(running_labels),-1))
        running_preds=np.reshape(running_preds, (len(running_preds),-1))
        print(f"El reshapeo del array {running_preds.shape}")
        optimal_thresholds = thresholds_search(running_labels,running_preds)
        running_probs = running_preds
        running_preds = np.stack([
            np.where(running_preds[:, cls] >= optimal_thresholds[cls], 1, 0) for cls in range(running_preds.shape[1])
        ]).transpose()
        ########################################################
    
    # print(f"Forma de las running_labels: {running_labels.shape}\n")
    print(f"Forma de las running_labels:\n")
    print(running_labels)
    # print(f"\nForma de las running_preds: {running_preds.shape}\n")
    print(f"\nForma de las running_preds:\n")
    print(running_preds)
    # print(f"\nForma de las running_probs: {running_probs.shape}\n")
    print(f"\nForma de las running_probs:\n")
    print(running_probs)
    print(f"\noptimal_thresholds utilizados:\n")
    print(optimal_thresholds)  
